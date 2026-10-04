"""Canonical session keys, snapshot recovery, and non-destructive state handling."""

import asyncio
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from gh_dispatch.errors import StateDatabaseError
from gh_dispatch.models import RunningCodingSession
from gh_dispatch.repositories import RunningSessionRepository
from tests.helpers import issue_task


async def test_round_trip_keeps_independent_automations_separate(tmp_path: Path) -> None:
    repository = RunningSessionRepository(tmp_path / "state.sqlite3")
    first = RunningCodingSession(
        task=issue_task(tmp_path, name="first"), session_id="first", message="Work"
    )
    second = RunningCodingSession(
        task=issue_task(tmp_path, name="second"), session_id="second", message="Review"
    )
    await repository.save(first)
    await repository.save(second)
    assert await repository.get(first.task) == first
    assert len(await repository.list_all()) == 2
    await repository.delete(first.task)
    assert await repository.get(first.task) is None
    assert await repository.get(second.task) == second


@pytest.mark.parametrize("contents", [b"not a database", None])
async def test_incompatible_files_are_preserved(tmp_path: Path, contents: bytes | None) -> None:
    path = tmp_path / "state.sqlite3"
    if contents is None:
        with closing(sqlite3.connect(path)) as connection, connection:
            connection.execute("CREATE TABLE unrelated (value TEXT)")
            connection.execute("INSERT INTO unrelated VALUES ('preserve me')")
    else:
        path.write_bytes(contents)
    original = path.read_bytes()
    with pytest.raises(StateDatabaseError, match="preserved"):
        await RunningSessionRepository(path).list_all()
    assert path.read_bytes() == original


async def test_expired_records_are_removed_and_invalid_payloads_preserved(tmp_path: Path) -> None:
    path = tmp_path / "state.sqlite3"
    repository = RunningSessionRepository(path)
    session = RunningCodingSession(task=issue_task(tmp_path), session_id="native", message="Work")
    await repository.save(session, ttl_seconds=0.001)
    await asyncio.sleep(0.01)
    assert await repository.get(session.task) is None
    await repository.save(session)
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("UPDATE key_value_state SET content = 'invalid JSON'")
    with pytest.raises(StateDatabaseError):
        await repository.list_all()
    with closing(sqlite3.connect(path)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM key_value_state").fetchone()[0] == 1
