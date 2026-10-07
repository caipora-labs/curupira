"""CLI validation, argument contracts, and user-facing failure statuses."""

import sys
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from curupira.cli import CliOptions, _batch_stream, _build_parser, _program_name, async_main
from curupira.config import load_settings
from curupira.models import Task
from curupira.runtime import DispatchInstanceLock, dispatch_home
from curupira.tasks.base import TaskFeed
from tests.helpers import issue_task


class SequenceFeed(TaskFeed):
    """Return finite batches in order for batch-mode tests."""

    def __init__(self, batches: list[list[Task]]) -> None:
        self.batches = batches

    async def poll(self, *, preview: bool = False) -> list[Task]:
        return self.batches.pop(0) if self.batches else []

    async def stream(self) -> AsyncIterator[Task]:
        for batch in self.batches:
            for task in batch:
                yield task


def test_program_name_follows_the_invoked_console_script(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _program_name("curupira") == "curupira"
    assert _program_name("/usr/local/bin/curu") == "curu"
    assert _program_name("/usr/local/bin/curu.EXE") == "curu"
    assert _program_name("/usr/bin/pytest") == "curupira"

    monkeypatch.setattr(sys, "argv", ["/usr/local/bin/curu"])
    assert _build_parser().format_help().startswith("usage: curu")
    monkeypatch.setattr(sys, "argv", ["/usr/local/bin/curupira"])
    assert _build_parser().format_help().startswith("usage: curupira")


def test_parser_supports_source_independent_commands(tmp_path: Path) -> None:
    parsed = _build_parser().parse_args(
        ["--config", str(tmp_path / "config.toml"), "run", "--dry-run"]
    )
    options = CliOptions.model_validate(vars(parsed))
    assert options.command == "run"
    assert options.dry_run
    assert _build_parser().parse_args(["watch"]).command == "watch"
    batch = _build_parser().parse_args(["batch", "--size", "2"])
    assert CliOptions.model_validate(vars(batch)).size == 2


@pytest.mark.parametrize("value", ["0", "-1", "nope"])
def test_batch_size_must_be_a_positive_integer(value: str) -> None:
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["batch", "--size", value])


async def test_batch_stream_drains_each_feed_until_empty(tmp_path: Path) -> None:
    first, second = issue_task(tmp_path, 1), issue_task(tmp_path, 2)
    feed = SequenceFeed([[first], [second]])

    assert [task async for task in _batch_stream([feed], None)] == [first, second]


async def test_batch_stream_stops_at_size_even_when_more_tasks_exist(tmp_path: Path) -> None:
    tasks = [issue_task(tmp_path, number) for number in range(1, 4)]
    feed = SequenceFeed([tasks])

    assert [task async for task in _batch_stream([feed], 2)] == tasks[:2]


async def test_batch_stream_exits_cleanly_for_empty_queue() -> None:
    assert [task async for task in _batch_stream([SequenceFeed([])], None)] == []


def test_parser_defaults_to_central_settings_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    parsed = _build_parser().parse_args(["validate"])

    assert parsed.config == tmp_path / ".curupira" / "settings.toml"


async def test_default_configuration_is_loaded_from_user_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    config = tmp_path / ".curupira" / "settings.toml"
    config.parent.mkdir()
    config.write_text(
        '[coding_agents.automations.daily]\ntrigger_type="cron"\nrepo="acme/api"\n'
        'schedule="0 9 * * *"\nprompt="Maintain ${repo}"\n',
        encoding="utf-8",
    )
    options = CliOptions.model_validate(vars(_build_parser().parse_args(["validate"])))

    assert await async_main(options) == 0
    assert "Configuration is valid (1 automations" in capsys.readouterr().out


async def test_dispatch_refuses_to_run_when_another_instance_holds_lock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    lock = DispatchInstanceLock(dispatch_home() / "dispatch.lock")
    lock.acquire()
    try:
        options = CliOptions(command="run", config=tmp_path / "missing.toml")

        assert await async_main(options) == 1
        assert "another curupira process is already running" in capsys.readouterr().err
    finally:
        lock.release()


async def test_validate_is_side_effect_free_for_cron_only_configuration(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        '[settings]\nstate_db_path="state.sqlite3"\n'
        '[coding_agents.automations.daily]\ntrigger_type="cron"\nrepo="acme/api"\n'
        'schedule="0 9 * * *"\nprompt="Maintain ${repo}"\n',
        encoding="utf-8",
    )
    assert await async_main(CliOptions(command="validate", config=path)) == 0
    assert "1 automations" in capsys.readouterr().out
    assert sorted(item.name for item in tmp_path.iterdir()) == ["config.toml"]


async def test_example_configuration_is_valid(tmp_path: Path) -> None:
    example = Path(__file__).resolve().parents[1] / "curupira.example.toml"
    settings = await load_settings(example)
    assert sorted(settings.resolve_automations()) == [
        "resolve-ready-issues",
        "review-pull-requests",
        "weekly-maintenance",
    ]
    assert list(tmp_path.iterdir()) == []


async def test_configuration_error_has_actionable_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert await async_main(CliOptions(command="run", config=tmp_path / "absent.toml")) == 2
    assert "configuration file not found" in capsys.readouterr().err
