"""Configuration file watching and hot-reload during continuous dispatch."""

import asyncio
from collections.abc import AsyncIterator, Callable, Sequence
from pathlib import Path

import pytest

from curupira.config import ApplicationSettings, load_settings
from curupira.config_reload import (
    config_mtime_ns,
    run_continuous_dispatch,
    wait_for_config_change,
)
from curupira.models import ExecutionSettings, Task
from curupira.scheduler import TaskScheduler
from curupira.tasks.base import TaskFeed
from curupira.telemetry import TaskTelemetry
from tests.fakes import FakeVersionControl
from tests.helpers import issue_task
from tests.test_scheduler import ControlledAdapter, executor, stream


def _write_config(path: Path, *, max_active_tasks: int = 1) -> None:
    path.write_text(
        f"[settings]\nmax_active_tasks = {max_active_tasks}\n"
        f'workspace_dir = "{path.parent / "workspaces"}"\n'
        f'state_db_path = "{path.parent / "state.sqlite3"}"\n'
        "[repositories.api]\n"
        'remote = "https://github.com/acme/api.git"\n'
        "[agents.defaults]\n"
        'profile = "opencode"\n'
        "[agents.profiles.opencode]\n"
        'provider = "opencode"\n'
        "[automations.daily]\n"
        'trigger_type = "cron"\n'
        'repository = "api"\n'
        'schedule = "0 9 * * *"\n'
        'prompt = "Maintain ${repository}"\n',
        encoding="utf-8",
    )


class BlockingFeed(TaskFeed):
    """Yield a fixed sequence, then wait until cancelled (watch-style stream)."""

    def __init__(self, tasks: Sequence[Task]) -> None:
        self._tasks = list(tasks)

    async def poll(self, *, preview: bool = False) -> list[Task]:
        return list(self._tasks)

    async def stream(self) -> AsyncIterator[Task]:
        for task in self._tasks:
            yield task
        await asyncio.Event().wait()


class EmptyFeed(TaskFeed):
    """Finite empty stream so a reload cycle can exit cleanly in tests."""

    async def poll(self, *, preview: bool = False) -> list[Task]:
        return []

    async def stream(self) -> AsyncIterator[Task]:
        return
        yield  # pragma: no cover


async def _wait_until(predicate: Callable[[], bool], *, deadline_seconds: float = 5.0) -> None:
    """Poll a zero-argument callable until it becomes true."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + deadline_seconds
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition was not met before timeout")


async def test_wait_for_config_change_returns_new_mtime(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    _write_config(config)
    initial = config_mtime_ns(config)
    assert initial is not None

    async def touch() -> None:
        await asyncio.sleep(0.01)
        _write_config(config, max_active_tasks=2)

    touch_task = asyncio.create_task(touch())
    updated = await wait_for_config_change(
        config, since_mtime_ns=initial, poll_interval_seconds=0.01
    )
    await touch_task
    assert updated != initial


async def test_request_reload_finishes_active_and_discards_pending(tmp_path: Path) -> None:
    adapter = ControlledAdapter()
    scheduler = TaskScheduler(ExecutionSettings(max_active_tasks=1), executor(tmp_path, adapter))
    first = issue_task(tmp_path, 1)
    second = issue_task(tmp_path, 2)
    running = asyncio.create_task(scheduler.run(stream([first, second])))
    await asyncio.wait_for(adapter.started.wait(), 5)
    assert len(adapter.requests) == 1

    scheduler.request_reload()
    await asyncio.sleep(0.05)
    assert len(adapter.requests) == 1
    assert scheduler.reload_requested

    adapter.release.set()
    await asyncio.wait_for(running, 5)
    assert len(adapter.requests) == 1
    assert scheduler.failed_tasks == 0


async def test_resume_is_ignored_while_reload_is_requested(tmp_path: Path) -> None:
    adapter = ControlledAdapter()
    scheduler = TaskScheduler(ExecutionSettings(), executor(tmp_path, adapter))
    running = asyncio.create_task(scheduler.run(stream([issue_task(tmp_path)])))
    await asyncio.wait_for(adapter.started.wait(), 5)
    scheduler.request_reload()
    scheduler.resume()
    assert scheduler.paused
    adapter.release.set()
    await asyncio.wait_for(running, 5)


async def test_continuous_dispatch_reloads_after_in_flight_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "settings.toml"
    _write_config(config, max_active_tasks=1)
    settings = await load_settings(config)
    adapter = ControlledAdapter()
    first = issue_task(tmp_path / "workspaces", 1)
    cycles = {"n": 0}
    reloaded: list[ApplicationSettings] = []
    holders: dict[str, TaskScheduler | None] = {"scheduler": None}

    def fake_feeds(*_args: object, **_kwargs: object) -> list[TaskFeed]:
        cycles["n"] += 1
        if cycles["n"] == 1:
            return [BlockingFeed([first])]
        return [EmptyFeed()]

    monkeypatch.setattr("curupira.config_reload.create_task_feeds", fake_feeds)

    async def mutate_and_finish() -> None:
        await asyncio.wait_for(adapter.started.wait(), 5)
        assert len(adapter.requests) == 1
        _write_config(config, max_active_tasks=3)

        def reload_ready() -> bool:
            scheduler = holders["scheduler"]
            return scheduler is not None and scheduler.reload_requested

        await _wait_until(reload_ready)
        assert len(adapter.requests) == 1
        adapter.release.set()

    helper = asyncio.create_task(mutate_and_finish())
    code = await asyncio.wait_for(
        run_continuous_dispatch(
            settings,
            config,
            version_control=FakeVersionControl(),
            telemetry=TaskTelemetry(),
            adapter_factory=lambda _profile: adapter,
            on_settings_reloaded=reloaded.append,
            on_scheduler_ready=lambda scheduler: holders.__setitem__("scheduler", scheduler),
            poll_interval_seconds=0.02,
        ),
        timeout=10,
    )
    await helper
    assert code == 0
    assert cycles["n"] >= 2
    assert reloaded
    assert reloaded[0].settings.max_active_tasks == 3
    assert len(adapter.requests) == 1


async def test_invalid_reload_waits_for_valid_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "settings.toml"
    _write_config(config)
    settings = await load_settings(config)
    adapter = ControlledAdapter()
    cycles = {"n": 0}
    reloaded: list[int] = []
    holders: dict[str, TaskScheduler | None] = {"scheduler": None}

    def fake_feeds(*_args: object, **_kwargs: object) -> list[TaskFeed]:
        cycles["n"] += 1
        if cycles["n"] == 1:
            return [BlockingFeed([issue_task(tmp_path / "workspaces", 1)])]
        return [EmptyFeed()]

    monkeypatch.setattr("curupira.config_reload.create_task_feeds", fake_feeds)

    async def mutate() -> None:
        await asyncio.wait_for(adapter.started.wait(), 5)
        config.write_text("this is not valid toml [[[", encoding="utf-8")

        def reload_ready() -> bool:
            scheduler = holders["scheduler"]
            return scheduler is not None and scheduler.reload_requested

        await _wait_until(reload_ready)
        adapter.release.set()
        await _wait_until(lambda: cycles["n"] == 1 and not reloaded)
        await asyncio.sleep(0.05)
        assert reloaded == []
        _write_config(config, max_active_tasks=4)
        await _wait_until(lambda: reloaded == [4])

    helper = asyncio.create_task(mutate())
    code = await asyncio.wait_for(
        run_continuous_dispatch(
            settings,
            config,
            version_control=FakeVersionControl(),
            telemetry=TaskTelemetry(),
            adapter_factory=lambda _profile: adapter,
            on_settings_reloaded=lambda loaded: reloaded.append(loaded.settings.max_active_tasks),
            on_scheduler_ready=lambda scheduler: holders.__setitem__("scheduler", scheduler),
            poll_interval_seconds=0.02,
        ),
        timeout=10,
    )
    await helper
    assert code == 0
    assert reloaded == [4]
