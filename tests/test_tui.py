"""Unit tests for TUI formatting, status bookkeeping, and dashboard mount."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from textual.widgets import Label

from curupira.config import ApplicationSettings
from curupira.models import Task, TaskIdentity
from curupira.models.items import CronItem
from curupira.telemetry import TaskTelemetry
from curupira.tui.app import OrchestratorApp
from curupira.tui.formatting import (
    activity_near_limit,
    format_elapsed,
    format_memory,
    provider_label,
    task_description,
    task_display_id,
)
from curupira.tui.status import OrchestratorStatus
from curupira.vcs.github_cli import GitHubCliVersionControl
from tests.helpers import issue_task, resolved_automation


def test_provider_labels_match_dashboard_names() -> None:
    assert provider_label("cursor") == "Cursor"
    assert provider_label("codex") == "Codex"
    assert provider_label("opencode") == "OpenCode"
    assert provider_label("claude") == "Claude Code"
    assert provider_label("custom") == "custom"


def test_format_elapsed_and_memory() -> None:
    started = datetime(2026, 10, 8, 12, 0, 0, tzinfo=UTC)
    now = datetime(2026, 10, 8, 12, 2, 20, tzinfo=UTC)
    assert format_elapsed(started, now=now) == "00:02:20"
    assert format_memory(6_442_450_944, 17_179_869_184) == "6.0 GB / 16.0 GB"


def test_activity_near_limit_threshold() -> None:
    assert not activity_near_limit(4, 10)
    assert activity_near_limit(8, 10)
    assert activity_near_limit(5, 5)
    assert not activity_near_limit(0, 0)


def test_task_display_helpers(tmp_path: Path) -> None:
    task = issue_task(tmp_path, 101)
    assert task_display_id(task) == "#101"
    assert task_description(task) == "Task 101"

    cron = Task(
        identity=TaskIdentity(
            automation_id="daily", repo="acme/api", task_type="cron", id="1696118400"
        ),
        automation=resolved_automation(tmp_path, "daily", "cron"),
        title="   ",
        url="https://example.invalid/cron",
        item=CronItem(),
        scheduled_for=datetime(2023, 10, 1, 0, 0, tzinfo=UTC),
    )
    assert task_description(cron) == "daily cron"


def test_orchestrator_status_tracks_elapsed_timers(tmp_path: Path) -> None:
    first = issue_task(tmp_path, 1)
    second = issue_task(tmp_path, 2)
    status = OrchestratorStatus()
    status.update((first, second), limit=10)
    assert len(status.rows()) == 2
    assert status.limit == 10

    status.update((first,), limit=10)
    rows = status.rows()
    assert len(rows) == 1
    assert rows[0].display_id == "#1"
    assert rows[0].provider == "OpenCode"


@pytest.mark.asyncio
async def test_orchestrator_app_mounts_dashboard_panels(tmp_path: Path) -> None:
    settings = ApplicationSettings.model_validate(
        {
            "settings": {
                "state_db_path": str(tmp_path / "state.sqlite3"),
                "workspace_dir": str(tmp_path / "workspaces"),
                "max_active_tasks": 10,
            },
            "coding_agents": {
                "automations": {
                    "daily": {
                        "trigger_type": "cron",
                        "repo": "acme/api",
                        "schedule": "0 9 * * *",
                        "prompt": "Maintain ${repo}",
                    }
                }
            },
        }
    )
    app = OrchestratorApp(settings, GitHubCliVersionControl(), TaskTelemetry())

    async def _idle_scheduler() -> None:
        return None

    app._run_scheduler = _idle_scheduler  # type: ignore[method-assign]
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        labels = [str(widget.renderable) for widget in app.query(Label)]
        assert "MÉTRICAS DO SISTEMA" in labels
        assert "AGENTES EM EXECUÇÃO (0 de 10 ativos)" in labels
        assert "LOGS DO ORQUESTRADOR" in labels
        app.exit(0)
