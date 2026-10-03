"""Typed SQLite repository for cron creation and execution timestamps."""

from __future__ import annotations

import asyncio
import sqlite3
import time
from contextlib import closing
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from gh_dispatch.models import CronRunState, SelectedTask
from gh_dispatch.repositories.key_value import _SQLiteJsonRepository
from gh_dispatch.repositories.sessions import RunningSessionRepository


class CronScheduleRepository(_SQLiteJsonRepository[CronRunState]):
    """Persist each cron job's stable creation date and execution watermark."""

    _ENTITY_NAME = "cron_schedule_state"
    _MODEL = CronRunState

    def __init__(self, database_path: Path) -> None:
        super().__init__(database_path)

    async def get_or_create(self, job_id: str, created_at: datetime) -> CronRunState:
        await self._ensure_initialized()
        return await asyncio.to_thread(self._get_or_create_sync, job_id, created_at)

    async def state(self, job_id: str) -> CronRunState | None:
        return await self._get_value(job_id)

    async def set_pending(
        self,
        job_id: str,
        scheduled_for: datetime,
    ) -> CronRunState | None:
        await self._ensure_initialized()
        return await asyncio.to_thread(self._set_pending_sync, job_id, scheduled_for)

    async def mark_started(self, job_id: str, started_at: datetime) -> None:
        state = await self._get_value(job_id)
        if state is None:
            return
        await self._save_value(
            job_id,
            state.model_copy(update={"last_execution_at": started_at}),
        )

    async def complete_run(
        self,
        job_id: str,
        task: SelectedTask,
        session_repository: RunningSessionRepository,
    ) -> None:
        """Atomically clear a completed cron occurrence and its active session."""
        await self._ensure_initialized()
        await session_repository._ensure_initialized()
        if self._database_path.resolve() != session_repository._database_path.resolve():
            raise ValueError("cron and session repositories must use the same state database")
        await asyncio.to_thread(
            self._complete_run_sync,
            job_id,
            session_repository._ENTITY_NAME,
            session_repository._record_key(task),
        )

    def _get_or_create_sync(self, job_id: str, created_at: datetime) -> CronRunState:
        with closing(sqlite3.connect(self._database_path, timeout=30)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                f"SELECT ttl, content FROM {self._TABLE_NAME} WHERE entity = ? AND id = ?",
                (self._ENTITY_NAME, job_id),
            ).fetchone()
            if row is not None:
                expires_at, content = row
                if expires_at is None or expires_at > time.time():
                    try:
                        state = CronRunState.model_validate_json(content)
                        connection.commit()
                        return state
                    except ValidationError:
                        pass
                connection.execute(
                    f"DELETE FROM {self._TABLE_NAME} WHERE entity = ? AND id = ?",
                    (self._ENTITY_NAME, job_id),
                )

            state = CronRunState(job_id=job_id, created_at=created_at)
            connection.execute(
                f"""INSERT INTO {self._TABLE_NAME} (entity, id, ttl, content)
                    VALUES (?, ?, NULL, ?)""",
                (self._ENTITY_NAME, job_id, state.model_dump_json()),
            )
            connection.commit()
            return state

    def _set_pending_sync(
        self,
        job_id: str,
        scheduled_for: datetime,
    ) -> CronRunState | None:
        with closing(sqlite3.connect(self._database_path, timeout=30)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                f"SELECT content FROM {self._TABLE_NAME} WHERE entity = ? AND id = ?",
                (self._ENTITY_NAME, job_id),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            try:
                state = CronRunState.model_validate_json(row[0])
            except ValidationError:
                connection.execute(
                    f"DELETE FROM {self._TABLE_NAME} WHERE entity = ? AND id = ?",
                    (self._ENTITY_NAME, job_id),
                )
                connection.commit()
                return None
            if state.pending_scheduled_for is not None:
                connection.commit()
                return state
            if state.last_scheduled_for is not None and scheduled_for <= state.last_scheduled_for:
                connection.commit()
                return None

            state = state.model_copy(
                update={
                    "pending_scheduled_for": scheduled_for,
                    "last_scheduled_for": scheduled_for,
                }
            )
            connection.execute(
                f"UPDATE {self._TABLE_NAME} SET content = ? WHERE entity = ? AND id = ?",
                (state.model_dump_json(), self._ENTITY_NAME, job_id),
            )
            connection.commit()
            return state

    def _complete_run_sync(
        self,
        job_id: str,
        session_entity: str,
        session_record_id: str,
    ) -> None:
        with closing(sqlite3.connect(self._database_path, timeout=30)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                f"SELECT content FROM {self._TABLE_NAME} WHERE entity = ? AND id = ?",
                (self._ENTITY_NAME, job_id),
            ).fetchone()
            if row is not None:
                try:
                    state = CronRunState.model_validate_json(row[0])
                except ValidationError:
                    state = None
                if state is not None:
                    connection.execute(
                        f"UPDATE {self._TABLE_NAME} SET content = ? WHERE entity = ? AND id = ?",
                        (
                            state.model_copy(
                                update={"pending_scheduled_for": None}
                            ).model_dump_json(),
                            self._ENTITY_NAME,
                            job_id,
                        ),
                    )
            connection.execute(
                f"DELETE FROM {self._TABLE_NAME} WHERE entity = ? AND id = ?",
                (session_entity, session_record_id),
            )
            connection.commit()
