"""Typed SQLite storage for resumable native coding-agent sessions."""

from curupi.models import RunningCodingSession, Task
from curupi.storage.key_value import _SQLiteJsonRepository


class RunningSessionRepository(_SQLiteJsonRepository[RunningCodingSession]):
    """Store session snapshots under the canonical automation-scoped identity."""

    _ENTITY_NAME = "running_coding_sessions"
    _MODEL = RunningCodingSession

    async def save(
        self, session: RunningCodingSession, *, ttl_seconds: float | None = None
    ) -> None:
        """Persist the original task and its native session identifier."""
        await self._save_value(session.task.identity.key, session, ttl_seconds=ttl_seconds)

    async def get(self, task: Task) -> RunningCodingSession | None:
        """Find a session for precisely this automation and occurrence."""
        return await self._get_value(task.identity.key)

    async def list_all(self) -> list[RunningCodingSession]:
        """Return resumable sessions without altering valid records."""
        return await self._list_values()

    async def delete(self, task: Task) -> None:
        """Remove only the completed task's session."""
        await self._delete_value(task.identity.key)
