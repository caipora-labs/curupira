"""Transactional creation, claiming, and completion of cron occurrences."""

import asyncio
import sqlite3
from contextlib import closing
from datetime import datetime

from opscli.models import CronRunState, Task
from opscli.repositories.key_value import _SQLiteJsonRepository
from opscli.repositories.sessions import RunningSessionRepository


class CronScheduleRepository(_SQLiteJsonRepository[CronRunState]):
    """Persist one pending occurrence and a stable creation time per automation."""

    _ENTITY_NAME = "cron_schedule_state"
    _MODEL = CronRunState

    async def get_or_create(self, automation_id: str, created_at: datetime) -> CronRunState:
        """Record a stable start date only on the first real discovery cycle."""
        state = CronRunState(automation_id=automation_id, created_at=created_at)
        await self._ensure_initialized()
        return await asyncio.to_thread(self._get_or_create_sync, state)

    async def state(self, automation_id: str) -> CronRunState | None:
        """Return validated state, initializing the application's database if needed."""
        return await self._get_value(automation_id)

    async def preview_state(self, automation_id: str) -> CronRunState | None:
        """Read scheduling state without any write or schema initialization."""
        return await self._peek_value(automation_id)

    async def set_pending(self, automation_id: str, scheduled_for: datetime) -> CronRunState | None:
        """Atomically claim an occurrence without replacing one already pending."""
        await self._ensure_initialized()
        return await asyncio.to_thread(self._set_pending_sync, automation_id, scheduled_for)

    async def mark_started(self, automation_id: str, started_at: datetime) -> None:
        """Record execution start while preserving the claimed occurrence."""
        state = await self._get_value(automation_id)
        if state is not None:
            data = state.model_dump()
            data["last_execution_at"] = started_at
            await self._save_value(automation_id, CronRunState.model_validate(data))

    async def complete_run(self, task: Task, sessions: RunningSessionRepository) -> None:
        """Atomically clear the exact completed occurrence and its active session."""
        await self._ensure_initialized()
        await sessions._ensure_initialized()
        if self._database_path.resolve() != sessions._database_path.resolve():
            raise ValueError("cron and session repositories must use the same state database")
        await asyncio.to_thread(self._complete_sync, task, sessions._ENTITY_NAME)

    def _get_or_create_sync(self, new_state: CronRunState) -> CronRunState:
        with closing(sqlite3.connect(self._database_path, timeout=30)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                f"SELECT content FROM {self._TABLE_NAME} WHERE entity = ? AND id = ?",
                (self._ENTITY_NAME, new_state.automation_id),
            ).fetchone()
            if row is not None:
                return CronRunState.model_validate_json(row[0])
            connection.execute(
                f"INSERT INTO {self._TABLE_NAME} (entity, id, ttl, content) VALUES (?, ?, NULL, ?)",
                (self._ENTITY_NAME, new_state.automation_id, new_state.model_dump_json()),
            )
            connection.commit()
            return new_state

    def _set_pending_sync(self, automation_id: str, occurrence: datetime) -> CronRunState | None:
        with closing(sqlite3.connect(self._database_path, timeout=30)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                f"SELECT content FROM {self._TABLE_NAME} WHERE entity = ? AND id = ?",
                (self._ENTITY_NAME, automation_id),
            ).fetchone()
            if row is None:
                return None
            state = CronRunState.model_validate_json(row[0])
            if state.pending_scheduled_for is not None:
                return state
            if state.last_scheduled_for is not None and occurrence <= state.last_scheduled_for:
                return None
            data = state.model_dump()
            data.update(pending_scheduled_for=occurrence, last_scheduled_for=occurrence)
            claimed = CronRunState.model_validate(data)
            connection.execute(
                f"UPDATE {self._TABLE_NAME} SET content = ? WHERE entity = ? AND id = ?",
                (claimed.model_dump_json(), self._ENTITY_NAME, automation_id),
            )
            connection.commit()
            return claimed

    def _complete_sync(self, task: Task, session_entity: str) -> None:
        with closing(sqlite3.connect(self._database_path, timeout=30)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                f"SELECT content FROM {self._TABLE_NAME} WHERE entity = ? AND id = ?",
                (self._ENTITY_NAME, task.identity.automation_id),
            ).fetchone()
            if row is not None:
                state = CronRunState.model_validate_json(row[0])
                if state.pending_scheduled_for == task.scheduled_for:
                    data = state.model_dump()
                    data["pending_scheduled_for"] = None
                    completed = CronRunState.model_validate(data)
                    connection.execute(
                        f"UPDATE {self._TABLE_NAME} SET content = ? WHERE entity = ? AND id = ?",
                        (
                            completed.model_dump_json(),
                            self._ENTITY_NAME,
                            task.identity.automation_id,
                        ),
                    )
            connection.execute(
                f"DELETE FROM {self._TABLE_NAME} WHERE entity = ? AND id = ?",
                (session_entity, task.identity.key),
            )
            connection.commit()
