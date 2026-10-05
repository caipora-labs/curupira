"""Terminal-only rendering for the live task status line."""

import sys
from collections.abc import Sequence
from typing import TextIO

from gh_dispatch.models import Task


def format_task_status(tasks: Sequence[Task], limit: int) -> str:
    """Format active task names and their bounded concurrency count."""
    count = len(tasks)
    details = ""
    if count == 1:
        identity = tasks[0].identity
        if identity.task_type == "cron":
            details = f"{identity.automation_id} cron"
        else:
            details = f"{identity.automation_id} {identity.repo}#{identity.number}"
    prefix = f"{details} " if details else ""
    return f"\r{prefix}{count}/{limit}"


class TerminalTaskStatus:
    """Rewrite one status line on a terminal without sending it to log handlers."""

    def __init__(self, stream: TextIO = sys.stdout) -> None:
        self._stream = stream
        self._visible = False

    def update(self, tasks: Sequence[Task], limit: int) -> None:
        """Render active work, clearing an empty run status instead."""
        if not self._stream.isatty():
            return
        if not tasks:
            self.clear()
            return
        self._stream.write(f"{format_task_status(tasks, limit)}\x1b[K")
        self._stream.flush()
        self._visible = True

    def clear(self) -> None:
        """Erase the visible line before the command prints its result."""
        if self._visible:
            self._stream.write("\r\x1b[K")
            self._stream.flush()
            self._visible = False
