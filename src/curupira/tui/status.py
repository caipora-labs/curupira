"""Track active tasks and elapsed timers for the Textual dashboard."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from curupira.models import Task
from curupira.tui.formatting import (
    format_elapsed,
    provider_label,
    task_description,
    task_display_id,
)


@dataclass(frozen=True, slots=True)
class AgentRow:
    """One rendered row in the running-agents panel."""

    key: str
    display_id: str
    provider: str
    elapsed: str
    description: str


class OrchestratorStatus:
    """Mirror ``TerminalTaskStatus`` while retaining start times for elapsed timers."""

    def __init__(self) -> None:
        self.tasks: tuple[Task, ...] = ()
        self.limit = 0
        self._started_at: dict[str, datetime] = {}

    def update(self, tasks: Sequence[Task], limit: int) -> None:
        """Refresh the active snapshot and bookkeeping for newly arrived tasks."""
        self.limit = limit
        current = tuple(tasks)
        self.tasks = current
        keys = {task.identity.key for task in current}
        now = datetime.now(UTC)
        for task in current:
            self._started_at.setdefault(task.identity.key, now)
        for key in list(self._started_at):
            if key not in keys:
                del self._started_at[key]

    def rows(self, *, now: datetime | None = None) -> list[AgentRow]:
        """Build display rows with provider labels and elapsed timers."""
        current = now if now is not None else datetime.now(UTC)
        rows: list[AgentRow] = []
        for task in self.tasks:
            key = task.identity.key
            started = self._started_at.get(key, current)
            rows.append(
                AgentRow(
                    key=key,
                    display_id=task_display_id(task),
                    provider=provider_label(task.automation.profile.provider),
                    elapsed=format_elapsed(started, now=current),
                    description=task_description(task),
                )
            )
        return rows
