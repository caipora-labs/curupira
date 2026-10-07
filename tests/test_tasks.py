"""Source-neutral task identity and occurrence validation."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from curupi.models import Task, TaskIdentity
from tests.helpers import resolved_automation


def test_task_identity_accepts_string_card_ids_and_serializes_the_string() -> None:
    identity = TaskIdentity(
        automation_id="board",
        repo="acme/api",
        task_type="issue",
        id="66f6b55a1a2b3c4d5e6f7788",
    )

    assert identity.id == "66f6b55a1a2b3c4d5e6f7788"
    assert json.loads(identity.key) == [
        "board",
        "acme/api",
        "issue",
        "66f6b55a1a2b3c4d5e6f7788",
    ]


def test_task_identity_accepts_registered_extension_type_and_keeps_key_format() -> None:
    identity = TaskIdentity(
        automation_id="board", repo="acme/api", task_type="github-cli-pull-requests", id="42"
    )

    assert identity.key == '["board","acme/api","github-cli-pull-requests","42"]'


def test_task_identity_rejects_an_empty_id() -> None:
    with pytest.raises(ValidationError):
        TaskIdentity(automation_id="board", repo="acme/api", task_type="issue", id=" ")


def test_cron_identity_must_match_scheduled_timestamp_string(tmp_path: Path) -> None:
    scheduled_for = datetime(2026, 10, 4, 9, tzinfo=UTC)
    automation = resolved_automation(tmp_path, "maintenance", "cron")

    task = Task(
        identity=TaskIdentity(
            automation_id="maintenance",
            repo="acme/api",
            task_type="cron",
            id=str(int(scheduled_for.timestamp())),
        ),
        automation=automation,
        title="Maintenance",
        url="cron://maintenance",
        scheduled_for=scheduled_for,
    )
    assert task.identity.id == str(int(scheduled_for.timestamp()))

    with pytest.raises(ValidationError, match="cron identity must match"):
        Task(
            identity=task.identity.model_copy(update={"id": "wrong-occurrence"}),
            automation=automation,
            title="Maintenance",
            url="cron://maintenance",
            scheduled_for=scheduled_for,
        )
