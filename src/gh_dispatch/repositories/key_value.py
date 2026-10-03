"""Private SQLite-backed JSON model repository primitives."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)
ModelT = TypeVar("ModelT", bound=BaseModel)


class _SQLiteJsonRepository(Generic[ModelT]):
    """Typed JSON storage; concrete repositories provide a private entity namespace."""

    _ENTITY_NAME: str
    _TABLE_NAME = "key_value_state"
    _MODEL: type[ModelT]

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path.expanduser()
        self._initialized = False
        self._initialization_lock = asyncio.Lock()

    async def _save_value(
        self,
        record_id: str,
        value: ModelT,
        *,
        ttl_seconds: float | None = None,
    ) -> None:
        if ttl_seconds is not None and ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive when provided")
        await self._ensure_initialized()
        expires_at = time.time() + ttl_seconds if ttl_seconds is not None else None
        await asyncio.to_thread(
            self._save_sync,
            record_id,
            expires_at,
            value.model_dump_json(),
        )

    async def _get_value(self, record_id: str) -> ModelT | None:
        await self._ensure_initialized()
        return await asyncio.to_thread(self._get_sync, record_id)

    async def _list_values(self) -> list[ModelT]:
        await self._ensure_initialized()
        return await asyncio.to_thread(self._list_sync)

    async def _delete_value(self, record_id: str) -> None:
        await self._ensure_initialized()
        await asyncio.to_thread(self._delete_sync, record_id)

    async def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        async with self._initialization_lock:
            if self._initialized:
                return
            await asyncio.to_thread(self._ensure_schema_sync)
            self._initialized = True

    def _ensure_schema_sync(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(self._database_path, timeout=30)
            tables = self._user_tables(connection)
            if self._TABLE_NAME in tables:
                if not self._schema_is_compatible(connection):
                    connection.close()
                    connection = None
                    self._recreate_database()
                    self._create_schema()
                return
            if tables:
                connection.close()
                connection = None
                self._recreate_database()
            self._create_schema()
        except sqlite3.DatabaseError as error:
            if connection is not None:
                connection.close()
                connection = None
            message = str(error).lower()
            if "malformed" not in message and "not a database" not in message:
                raise
            logger.warning("Recreating invalid local state database %s", self._database_path)
            self._recreate_database()
            self._create_schema()
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _user_tables(connection: sqlite3.Connection) -> set[str]:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
        return {row[0] for row in rows}

    def _schema_is_compatible(self, connection: sqlite3.Connection) -> bool:
        rows = connection.execute(f"PRAGMA table_info({self._TABLE_NAME})").fetchall()
        actual = [(row[1], row[2].upper(), row[3], row[5]) for row in rows]
        expected = [
            ("entity", "TEXT", 1, 1),
            ("id", "TEXT", 1, 2),
            ("ttl", "REAL", 0, 0),
            ("content", "TEXT", 1, 0),
        ]
        return actual == expected

    def _create_schema(self) -> None:
        with closing(sqlite3.connect(self._database_path, timeout=30)) as connection:
            connection.execute(
                f"""CREATE TABLE IF NOT EXISTS {self._TABLE_NAME} (
                    entity TEXT NOT NULL,
                    id TEXT NOT NULL,
                    ttl REAL,
                    content TEXT NOT NULL,
                    PRIMARY KEY (entity, id)
                )"""
            )
            connection.commit()

    def _recreate_database(self) -> None:
        for path in (
            self._database_path,
            Path(f"{self._database_path}-wal"),
            Path(f"{self._database_path}-shm"),
        ):
            path.unlink(missing_ok=True)

    def _save_sync(self, record_id: str, expires_at: float | None, content: str) -> None:
        with closing(sqlite3.connect(self._database_path, timeout=30)) as connection:
            connection.execute(
                f"""INSERT INTO {self._TABLE_NAME} (entity, id, ttl, content)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(entity, id) DO UPDATE SET
                        ttl = excluded.ttl,
                        content = excluded.content""",
                (self._ENTITY_NAME, record_id, expires_at, content),
            )
            connection.commit()

    def _get_sync(self, record_id: str) -> ModelT | None:
        with closing(sqlite3.connect(self._database_path, timeout=30)) as connection:
            row = connection.execute(
                f"SELECT ttl, content FROM {self._TABLE_NAME} WHERE entity = ? AND id = ?",
                (self._ENTITY_NAME, record_id),
            ).fetchone()
            if row is None:
                return None
            expires_at, content = row
            if expires_at is not None and expires_at <= time.time():
                self._delete_with_connection(connection, record_id)
                return None
            try:
                return self._MODEL.model_validate_json(content)
            except ValidationError as error:
                logger.warning("Discarding invalid local state for %s: %s", record_id, error)
                self._delete_with_connection(connection, record_id)
                return None

    def _list_sync(self) -> list[ModelT]:
        now = time.time()
        result: list[ModelT] = []
        with closing(sqlite3.connect(self._database_path, timeout=30)) as connection:
            rows = connection.execute(
                f"SELECT id, ttl, content FROM {self._TABLE_NAME} WHERE entity = ?",
                (self._ENTITY_NAME,),
            ).fetchall()
            for record_id, expires_at, content in rows:
                if expires_at is not None and expires_at <= now:
                    self._delete_with_connection(connection, record_id)
                    continue
                try:
                    result.append(self._MODEL.model_validate_json(content))
                except ValidationError as error:
                    logger.warning("Discarding invalid local state for %s: %s", record_id, error)
                    self._delete_with_connection(connection, record_id)
        return result

    def _delete_sync(self, record_id: str) -> None:
        with closing(sqlite3.connect(self._database_path, timeout=30)) as connection:
            self._delete_with_connection(connection, record_id)

    def _delete_with_connection(self, connection: sqlite3.Connection, record_id: str) -> None:
        connection.execute(
            f"DELETE FROM {self._TABLE_NAME} WHERE entity = ? AND id = ?",
            (self._ENTITY_NAME, record_id),
        )
        connection.commit()
