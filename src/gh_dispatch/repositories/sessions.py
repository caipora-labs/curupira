"""Typed SQLite repository for running coding-agent sessions."""

from __future__ import annotations

from pathlib import Path

from gh_dispatch.models import RunningCodingSession, SelectedTask
from gh_dispatch.repositories.key_value import _SQLiteJsonRepository


class RunningSessionRepository(_SQLiteJsonRepository[RunningCodingSession]):
    """Store running sessions without exposing the private persistence entity."""

    _ENTITY_NAME = "running_coding_sessions"
    _MODEL = RunningCodingSession

    def __init__(self, database_path: Path) -> None:
        super().__init__(database_path)

    async def save(
        self,
        session: RunningCodingSession,
        *,
        ttl_seconds: float | None = None,
    ) -> None:
        await self._save_value(
            _record_id(session.task),
            session,
            ttl_seconds=ttl_seconds,
        )

    async def get(self, record: str | SelectedTask) -> RunningCodingSession | None:
        record_id = _record_id(record) if isinstance(record, SelectedTask) else record
        return await self._get_value(record_id)

    async def list_all(self) -> list[RunningCodingSession]:
        return await self._list_values()

    async def delete(self, record: str | SelectedTask) -> None:
        record_id = _record_id(record) if isinstance(record, SelectedTask) else record
        await self._delete_value(record_id)

    def _record_key(self, task: SelectedTask) -> str:
        return _record_id(task)


def _record_id(record: SelectedTask) -> str:
    if record.task_type == "cron":
        return f"{record.repository.repo}:cron:{record.cron_job_id}:{record.number}"
    return f"{record.repository.repo}:{record.task_type}:{record.number}"
