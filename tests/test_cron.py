from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from gh_dispatch.cron import CronWatcher
from gh_dispatch.models import (
    CronJobSettings,
    CronWatcherSettings,
    RunningCodingSession,
    SelectedTask,
)
from gh_dispatch.repositories import CronScheduleRepository, RunningSessionRepository


def job(**overrides: object) -> CronJobSettings:
    values: dict[str, object] = {
        "id": "daily-maintenance",
        "schedule": "* * * * *",
        "timezone": "UTC",
        "repo": "acme/api",
        "prompt": "Maintain ${repo} at ${task_number}",
    }
    values.update(overrides)
    return CronJobSettings.model_validate(values)


@pytest.mark.asyncio
async def test_cron_watcher_coalesces_missed_ticks_and_restores_pending_run(
    tmp_path: Path,
) -> None:
    current = datetime(2026, 10, 3, 9, 10, tzinfo=UTC)
    state_repository = CronScheduleRepository(tmp_path / "state.sqlite3")
    cron_job = job(
        start_date="2026-10-03T09:00:00+00:00",
        end_date="2026-10-03T09:05:00+00:00",
    )
    settings = CronWatcherSettings(jobs=[cron_job])

    first_watcher = CronWatcher(
        settings,
        state_repository,
        tmp_path / "workspaces",
        now=lambda: current,
    )
    first_run = await anext(first_watcher.watch())

    assert first_run.task_type == "cron"
    assert first_run.cron_job_id == "daily-maintenance"
    assert first_run.scheduled_for == datetime(2026, 10, 3, 9, 5, tzinfo=UTC)
    assert first_run.repository.repo == "acme/api"
    assert first_run.repository.prompt == "Maintain ${repo} at ${task_number}"
    assert first_run.scheduled_for is not None
    assert first_run.number == int(first_run.scheduled_for.timestamp())
    saved_state = await state_repository.state(cron_job.id)
    assert saved_state is not None
    assert saved_state.pending_scheduled_for == first_run.scheduled_for
    still_pending = await state_repository.set_pending(
        cron_job.id,
        datetime(2026, 10, 3, 9, 6, tzinfo=UTC),
    )
    assert still_pending is not None
    assert still_pending.pending_scheduled_for == first_run.scheduled_for

    restarted_watcher = CronWatcher(
        settings,
        state_repository,
        tmp_path / "workspaces",
        now=lambda: current,
    )
    restored_run = await anext(restarted_watcher.watch())

    assert restored_run == first_run


@pytest.mark.asyncio
async def test_cron_without_start_date_uses_persisted_creation_time(
    tmp_path: Path,
) -> None:
    current = [datetime(2026, 10, 3, 9, 0, 30, tzinfo=UTC)]
    sleep_calls = 0

    async def advance_to_next_minute(_seconds: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        current[0] = datetime(2026, 10, 3, 9, 1, tzinfo=UTC)

    cron_job = job()
    watcher = CronWatcher(
        CronWatcherSettings(jobs=[cron_job]),
        CronScheduleRepository(tmp_path / "state.sqlite3"),
        tmp_path / "workspaces",
        now=lambda: current[0],
        sleep=advance_to_next_minute,
    )

    first_run = await anext(watcher.watch())

    assert sleep_calls == 1
    assert first_run.scheduled_for == datetime(2026, 10, 3, 9, 1, tzinfo=UTC)

    restored_state = await CronScheduleRepository(tmp_path / "state.sqlite3").get_or_create(
        cron_job.id,
        datetime(2026, 10, 4, 12, 0, tzinfo=UTC),
    )
    assert restored_state.created_at == datetime(2026, 10, 3, 9, 0, 30, tzinfo=UTC)


def test_cron_job_validates_expression_timezone_and_date_window() -> None:
    with pytest.raises(ValidationError, match="five-field cron expression"):
        job(schedule="not a cron")

    with pytest.raises(ValidationError, match="unknown timezone"):
        job(timezone="Mars/Olympus")

    with pytest.raises(ValidationError, match="end_date must be greater"):
        job(
            start_date="2026-10-04T00:00:00+00:00",
            end_date="2026-10-03T00:00:00+00:00",
        )


@pytest.mark.asyncio
async def test_cron_completion_atomically_clears_pending_run_and_session(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "state.sqlite3"
    cron_job = job()
    scheduled_for = datetime(2026, 10, 3, 9, 5, tzinfo=UTC)
    cron_repository = CronScheduleRepository(database_path)
    session_repository = RunningSessionRepository(database_path)
    await cron_repository.get_or_create(cron_job.id, datetime(2026, 10, 3, 9, 0, tzinfo=UTC))
    await cron_repository.set_pending(cron_job.id, scheduled_for)
    await cron_repository.mark_started(cron_job.id, datetime(2026, 10, 3, 9, 5, 1, tzinfo=UTC))

    selected = SelectedTask(
        task_type="cron",
        repository=cron_job.repository_settings(),
        number=int(scheduled_for.timestamp()),
        title=cron_job.id,
        url=f"cron://{cron_job.id}",
        workspace_path=cron_job.workspace_path(tmp_path / "workspaces"),
        cron_job_id=cron_job.id,
        scheduled_for=scheduled_for,
    )
    session = RunningCodingSession(
        task=selected,
        session_id="ses_cron",
        message="Continue cron task",
    )
    await session_repository.save(session)

    await cron_repository.complete_run(cron_job.id, selected, session_repository)

    state = await cron_repository.state(cron_job.id)
    assert state is not None
    assert state.pending_scheduled_for is None
    assert state.last_execution_at == datetime(2026, 10, 3, 9, 5, 1, tzinfo=UTC)
    assert await session_repository.get(selected) is None
