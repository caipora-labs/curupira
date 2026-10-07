"""Shared concurrency, checkout exclusivity, failure observation, and recovery."""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from pathlib import Path

from typing_extensions import override

from opscli.agents.base import SessionStartedCallback
from opscli.executor import TaskExecutor
from opscli.models import CodingTaskRequest, ExecutionSettings, ProcessResult, Task
from opscli.scheduler import TaskScheduler
from opscli.storage import CronScheduleRepository, RunningSessionRepository
from tests.fakes import FakeGitHub, RecordingAdapter
from tests.helpers import issue_task, pull_request_task


async def stream(tasks: list[Task]) -> AsyncIterator[Task]:
    """Yield a finite set of tasks with cooperative checkpoints."""
    for task in tasks:
        yield task


class ControlledAdapter(RecordingAdapter):
    """Track concurrent writers and block work until the test releases it."""

    def __init__(self) -> None:
        super().__init__()
        self.active_paths: set[Path] = set()
        self.peak = 0
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    @override
    async def run_task(
        self,
        request: CodingTaskRequest,
        *,
        on_session_started: SessionStartedCallback | None = None,
    ) -> ProcessResult:
        assert request.cwd not in self.active_paths
        self.active_paths.add(request.cwd)
        self.peak = max(self.peak, len(self.active_paths))
        self.requests.append(request)
        if on_session_started is not None:
            await on_session_started(request.session_id or f"session-{len(self.requests)}")
        self.started.set()
        try:
            await self.release.wait()
            return ProcessResult(returncode=0)
        finally:
            self.active_paths.remove(request.cwd)


def executor(path: Path, adapter: RecordingAdapter) -> TaskExecutor:
    """Use real persistence with controlled provider and checkout boundaries."""
    database = path / "state.sqlite3"
    return TaskExecutor(
        ExecutionSettings(state_db_path=database),
        FakeGitHub(),
        RunningSessionRepository(database),
        CronScheduleRepository(database),
        adapter_factory=lambda _: adapter,
    )


async def test_different_checkouts_run_concurrently_and_same_checkout_is_serial(
    tmp_path: Path,
) -> None:
    adapter = ControlledAdapter()
    scheduler = TaskScheduler(ExecutionSettings(max_active_tasks=2), executor(tmp_path, adapter))
    tasks = [
        issue_task(tmp_path / "first", 1),
        pull_request_task(tmp_path / "first", 2),
        pull_request_task(tmp_path / "second", 3),
    ]
    running = asyncio.create_task(scheduler.run(stream(tasks)))
    await asyncio.wait_for(adapter.started.wait(), 1)
    for _ in range(100):
        if adapter.peak == 2:
            break
        await asyncio.sleep(0.001)
    assert adapter.peak == 2
    adapter.release.set()
    await asyncio.wait_for(running, 2)
    assert len(adapter.requests) == 3
    assert scheduler.failed_tasks == 0


async def test_cancellation_persists_and_resumes_original_session(tmp_path: Path) -> None:
    adapter = ControlledAdapter()
    configured = ExecutionSettings(max_active_tasks=1)
    scheduler = TaskScheduler(configured, executor(tmp_path, adapter))
    task = issue_task(tmp_path)
    running = asyncio.create_task(scheduler.run(stream([task])))
    await asyncio.wait_for(adapter.started.wait(), 1)
    running.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await running
    repository = RunningSessionRepository(tmp_path / "state.sqlite3")
    saved = await repository.list_all()
    assert len(saved) == 1
    assert saved[0].task == task
    resumed = RecordingAdapter()
    await TaskScheduler(configured, executor(tmp_path, resumed)).run(
        stream([task]), resume_sessions=saved
    )
    assert len(resumed.requests) == 1
    assert resumed.requests[0].session_id == saved[0].session_id
    assert await repository.list_all() == []


async def test_nonzero_exits_are_observed_without_stopping_other_tasks(tmp_path: Path) -> None:
    adapter = RecordingAdapter(returncode=7)
    scheduler = TaskScheduler(ExecutionSettings(), executor(tmp_path, adapter))
    await scheduler.run(stream([issue_task(tmp_path, 1), issue_task(tmp_path, 2)]))
    assert scheduler.failed_tasks == 2
