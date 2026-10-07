"""Private SQLite-backed JSON model repository primitives."""

from __future__ import annotations

import asyncio
import logging
import math
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from curupi.errors import StateDatabaseError

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
        if ttl_seconds is not None and (ttl_seconds <= 0 or not math.isfinite(ttl_seconds)):
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

    async def _peek_value(self, record_id: str) -> ModelT | None:
        """Read without creating a database, initializing schema, or expiring records."""
        return await asyncio.to_thread(self._peek_sync, record_id)

    def _peek_sync(self, record_id: str) -> ModelT | None:
        if not self._database_path.is_file():
            return None
        try:
            uri = self._database_path.resolve().as_uri() + "?mode=ro"
            with closing(sqlite3.connect(uri, uri=True, timeout=30)) as connection:
                if not self._schema_is_compatible(connection):
                    raise self._incompatible_database()
                row = connection.execute(
                    f"SELECT ttl, content FROM {self._TABLE_NAME} WHERE entity = ? AND id = ?",
                    (self._ENTITY_NAME, record_id),
                ).fetchone()
                if row is None or (row[0] is not None and row[0] <= time.time()):
                    return None
                return self._MODEL.model_validate_json(row[1])
        except (sqlite3.DatabaseError, ValidationError) as error:
            raise self._incompatible_database() from error

    def _incompatible_database(self) -> StateDatabaseError:
        return StateDatabaseError(
            f"Cannot safely read state database {self._database_path}. "
            "The file was preserved; choose a new state_db_path or inspect and back up this file."
        )

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
        try:
            with closing(sqlite3.connect(self._database_path, timeout=30)) as connection:
                tables = self._user_tables(connection)
                if self._TABLE_NAME in tables:
                    if not self._schema_is_compatible(connection):
                        raise self._incompatible_database()
                    return
                if tables:
                    raise self._incompatible_database()
            self._create_schema()
        except sqlite3.DatabaseError as error:
            raise self._incompatible_database() from error

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
                raise self._incompatible_database() from error

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
                    raise self._incompatible_database() from error
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
