from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Literal

import pytest

from gh_dispatch.models import RepositoryWorkspaceSettings, RunningCodingSession, SelectedTask
from gh_dispatch.repositories import RunningSessionRepository


def task(
    repo: str = "acme/api",
    task_type: Literal["issue", "pull_request"] = "issue",
    number: int = 42,
) -> SelectedTask:
    repository = RepositoryWorkspaceSettings(repo=repo)
    return SelectedTask(
        task_type=task_type,
        repository=repository,
        number=number,
        title=f"Task {number}",
        body="Details",
        url=f"https://github.com/{repo}/issues/{number}",
        workspace_path=Path("/tmp/acme/api"),
    )


def session_state(selected: SelectedTask, session_id: str) -> RunningCodingSession:
    return RunningCodingSession(
        task=selected,
        session_id=session_id,
        message=f"Handle task {selected.number}",
        model="openai/test-model",
    )


@pytest.mark.asyncio
async def test_repository_round_trips_typed_models_with_composite_ids(tmp_path: Path) -> None:
    repository = RunningSessionRepository(tmp_path / "state.sqlite3")
    issue = session_state(task(), "ses_issue")
    pull_request = session_state(task(task_type="pull_request"), "ses_pr")

    await repository.save(issue)
    await repository.save(pull_request)

    assert await repository.get(issue.task) == issue
    assert await repository.get(pull_request.task) == pull_request
    assert {item.session_id for item in await repository.list_all()} == {"ses_issue", "ses_pr"}

    await repository.delete(issue.task)

    assert await repository.get(issue.task) is None
    assert await repository.get(pull_request.task) == pull_request


@pytest.mark.asyncio
async def test_repository_expires_ttl_records(tmp_path: Path) -> None:
    repository = RunningSessionRepository(tmp_path / "state.sqlite3")
    saved = session_state(task(), "ses_expiring")

    await repository.save(saved, ttl_seconds=0.01)
    await asyncio.sleep(0.05)

    assert await repository.get(saved.task) is None
    assert await repository.list_all() == []


@pytest.mark.asyncio
async def test_repository_recreates_incompatible_database_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "state.sqlite3"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE key_value_state (old_value BLOB)")
        connection.execute("INSERT INTO key_value_state VALUES (x'00')")

    repository = RunningSessionRepository(database_path)

    assert await repository.list_all() == []
    saved = session_state(task(), "ses_after_recreate")
    await repository.save(saved)
    assert await repository.get(saved.task) == saved

    with sqlite3.connect(database_path) as connection:
        columns = [row[1] for row in connection.execute("PRAGMA table_info(key_value_state)")]
    assert columns == ["entity", "id", "ttl", "content"]
