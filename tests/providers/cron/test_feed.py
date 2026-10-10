"""Cron windows, read-only preview, coalescing, and occurrence claims."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from curupira.models import (
    CronAutomationConfiguration,
    CronRunState,
    PollingSettings,
    RunningCodingSession,
)
from curupira.providers.cron import CronTaskFeed, latest_due_occurrence
from curupira.storage import CronScheduleRepository, RunningSessionRepository
from tests.helpers import resolved_automation


async def test_preview_does_not_create_state_and_real_poll_coalesces(tmp_path: Path) -> None:
    database = tmp_path / "nested/state.sqlite3"
    repository = CronScheduleRepository(database)
    now = datetime(2026, 10, 3, 12, tzinfo=UTC)
    feed = CronTaskFeed(
        resolved_automation(tmp_path, "maintenance", "cron"),
        PollingSettings(),
        repository,
        now=lambda: now,
    )
    preview = await feed.poll(preview=True)
    assert preview[0].scheduled_for == datetime(2026, 10, 3, 9, tzinfo=UTC)
    assert not database.parent.exists()
    actual = await feed.poll()
    assert actual == preview
    assert await feed.poll() == []
    recovered = CronTaskFeed(feed.automation, PollingSettings(), repository, now=lambda: now)
    assert await recovered.poll() == actual


async def test_pending_occurrence_is_not_overwritten_and_completion_is_atomic(
    tmp_path: Path,
) -> None:
    database = tmp_path / "state.sqlite3"
    repository = CronScheduleRepository(database)
    sessions = RunningSessionRepository(database)
    now = datetime(2026, 10, 3, 12, tzinfo=UTC)
    feed = CronTaskFeed(
        resolved_automation(tmp_path, "maintenance", "cron"),
        PollingSettings(),
        repository,
        now=lambda: now,
    )
    task = (await feed.poll())[0]
    await sessions.save(RunningCodingSession(task=task, session_id="native", message="Maintain"))
    results = await asyncio.gather(*[repository.set_pending("maintenance", now) for _ in range(3)])
    assert all(
        state is not None and state.pending_scheduled_for == task.scheduled_for for state in results
    )
    await repository.complete_run(task, sessions)
    state = await repository.state("maintenance")
    assert state is not None
    assert state.pending_scheduled_for is None
    assert await sessions.list_all() == []


def test_timezone_window_is_inclusive_and_dst_uses_local_clock() -> None:
    config = CronAutomationConfiguration(
        repository="api",
        prompt="Maintain",
        schedule="0 9 * * *",
        timezone="Europe/Rome",
        start_date=datetime.fromisoformat("2026-10-24T09:00:00+02:00"),
        end_date=datetime.fromisoformat("2026-10-26T09:00:00+01:00"),
    )
    state = CronRunState(automation_id="maintenance", created_at=datetime(2026, 10, 1, tzinfo=UTC))
    assert latest_due_occurrence(config, state, datetime(2026, 10, 23, tzinfo=UTC)) is None
    assert latest_due_occurrence(config, state, datetime(2026, 10, 25, 10, tzinfo=UTC)) == datetime(
        2026, 10, 25, 8, tzinfo=UTC
    )
    assert latest_due_occurrence(config, state, datetime(2026, 11, 1, tzinfo=UTC)) == datetime(
        2026, 10, 26, 8, tzinfo=UTC
    )


async def test_readonly_preview_preserves_existing_state(tmp_path: Path) -> None:
    repository = CronScheduleRepository(tmp_path / "state.sqlite3")
    created = datetime(2026, 10, 1, tzinfo=UTC)
    await repository.get_or_create("maintenance", created)
    before = repository._database_path.read_bytes()
    preview = await repository.preview_state("maintenance")
    assert preview is not None
    assert preview.created_at == created
    assert repository._database_path.read_bytes() == before
