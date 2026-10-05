"""Terminal status formatting and output boundaries."""

from collections.abc import Sequence
from io import StringIO
from pathlib import Path

from typing_extensions import override

from gh_dispatch.models import Task
from gh_dispatch.status import TerminalTaskStatus, format_task_status
from tests.helpers import issue_task


class TerminalBuffer(StringIO):
    """String buffer that behaves like an interactive terminal."""

    @override
    def isatty(self) -> bool:
        return True


def test_status_formats_single_and_multiple_active_tasks(tmp_path: Path) -> None:
    first = issue_task(tmp_path, 17)
    second = issue_task(tmp_path, 18)

    assert format_task_status([first], 3) == "\rissues acme/api#17 1/3"
    assert format_task_status([first, second], 3) == "\r2/3"


def test_status_omits_idle_run_and_keeps_idle_watch_count() -> None:
    run_output = TerminalBuffer()
    TerminalTaskStatus(run_output).update((), 3)
    assert run_output.getvalue() == ""

    watch_output = TerminalBuffer()
    TerminalTaskStatus(watch_output, show_idle=True).update((), 3)
    assert watch_output.getvalue() == "\r0/3\x1b[K"


def test_status_clears_before_following_result_and_skips_non_terminal(tmp_path: Path) -> None:
    task = issue_task(tmp_path)
    terminal = TerminalBuffer()
    status = TerminalTaskStatus(terminal)
    status.update((task,), 1)
    status.clear()
    assert terminal.getvalue().endswith("\r\x1b[K")

    non_terminal = StringIO()
    TerminalTaskStatus(non_terminal).update((task,), 1)
    assert non_terminal.getvalue() == ""


def test_multiple_active_tasks_do_not_leak_task_names(tmp_path: Path) -> None:
    tasks: Sequence[Task] = [issue_task(tmp_path, 1), issue_task(tmp_path, 2)]
    line = format_task_status(tasks, 4)
    assert "acme/api" not in line
    assert line.endswith("2/4")
