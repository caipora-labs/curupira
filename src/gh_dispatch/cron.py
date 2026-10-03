"""Cron-triggered task stream with persistent missed-run coalescing."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from croniter import croniter

from gh_dispatch.models import CronJobSettings, CronRunState, CronWatcherSettings, SelectedTask
from gh_dispatch.repositories import CronScheduleRepository


class CronWatcher:
    """Yield one pending run per job, coalescing any missed cron occurrences."""

    def __init__(
        self,
        settings: CronWatcherSettings,
        state_repository: CronScheduleRepository,
        workspace_dir: Path,
        *,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._settings = settings
        self._state_repository = state_repository
        self._workspace_dir = workspace_dir
        self._now = now
        self._sleep = sleep
        self._emitted: dict[str, str] = {}

    async def watch(self) -> AsyncIterator[SelectedTask]:
        while True:
            now = _ensure_utc(self._now())
            discovered: list[SelectedTask] = []
            for job in self._settings.jobs:
                state = await self._state_repository.get_or_create(job.id, now)
                occurrence = state.pending_scheduled_for or _latest_due_occurrence(job, state, now)
                if occurrence is None:
                    continue

                if state.pending_scheduled_for is None:
                    claimed = await self._state_repository.set_pending(job.id, occurrence)
                    if claimed is None:
                        continue
                    occurrence = claimed.pending_scheduled_for
                    if occurrence is None:
                        continue

                run_key = _run_key(job.id, occurrence)
                if self._emitted.get(job.id) == run_key:
                    continue
                self._emitted[job.id] = run_key
                discovered.append(_make_task(job, occurrence, self._workspace_dir))

            if discovered:
                for task in discovered:
                    yield task
                continue

            await self._sleep(self._settings.poll_interval_seconds)


def _latest_due_occurrence(
    job: CronJobSettings,
    state: CronRunState,
    now: datetime,
) -> datetime | None:
    timezone = ZoneInfo(job.timezone)
    local_now = now.astimezone(timezone)
    start = job.start_date or state.created_at.astimezone(timezone)
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone)
    else:
        start = start.astimezone(timezone)

    first = (
        start
        if croniter.match(job.schedule, start)
        else croniter(job.schedule, start, ret_type=datetime).get_next(datetime)
    )
    ceiling = min(local_now, job.end_date) if job.end_date is not None else local_now
    if ceiling < first:
        return None

    latest = croniter(
        job.schedule,
        ceiling + timedelta(microseconds=1),
        ret_type=datetime,
    ).get_prev(datetime)
    if latest < first:
        return None
    if state.last_scheduled_for is not None and latest <= state.last_scheduled_for:
        return None
    return latest.astimezone(UTC)


def _make_task(job: CronJobSettings, occurrence: datetime, workspace_dir: Path) -> SelectedTask:
    repository = job.repository_settings()
    return SelectedTask(
        task_type="cron",
        repository=repository,
        number=int(occurrence.timestamp()),
        title=job.id,
        body=None,
        url=f"cron://{job.id}",
        workspace_path=repository.workspace_path(workspace_dir),
        cron_job_id=job.id,
        scheduled_for=occurrence,
    )


def _run_key(job_id: str, occurrence: datetime) -> str:
    return f"{job_id}:{occurrence.astimezone(UTC).isoformat()}"


def _ensure_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
