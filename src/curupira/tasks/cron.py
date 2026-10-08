"""Local cron task feed and schedule occurrence calculation."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from croniter import croniter

from curupira.models import (
    CronAutomationConfiguration,
    CronRunState,
    PollingSettings,
    ResolvedAutomation,
    Task,
    TaskIdentity,
)
from curupira.storage import CronScheduleRepository
from curupira.tasks.base import FeedDependencies, TaskFeed, Trigger
from curupira.tasks.registry import register


def utc_now() -> datetime:
    """Return an aware timestamp for injectable cron clocks."""
    return datetime.now(UTC)


class CronTaskFeed(TaskFeed):
    """Coalesce overdue ticks into one persisted pending occurrence."""

    def __init__(
        self,
        automation: ResolvedAutomation,
        polling: PollingSettings,
        repository: CronScheduleRepository,
        *,
        now: Callable[[], datetime] = utc_now,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.automation = automation
        self._polling = polling
        self._repository = repository
        self._now = now
        self._sleep = sleep
        self._emitted: str | None = None

    async def poll(self, *, preview: bool = False) -> list[Task]:
        """Preview without writes, or atomically claim an available occurrence."""
        config = self.automation.configuration
        if not isinstance(config, CronAutomationConfiguration):
            raise ValueError("cron feed requires a cron configuration")
        now = self._now().astimezone(UTC)
        name = self.automation.automation_id
        if preview:
            state = await self._repository.preview_state(name)
            state = state or CronRunState(automation_id=name, created_at=now)
        else:
            state = await self._repository.get_or_create(name, now)
        occurrence = state.pending_scheduled_for or latest_due_occurrence(config, state, now)
        if occurrence is None:
            return []
        if not preview and state.pending_scheduled_for is None:
            claimed = await self._repository.set_pending(name, occurrence)
            if claimed is None or claimed.pending_scheduled_for is None:
                return []
            occurrence = claimed.pending_scheduled_for
        identity = TaskIdentity(
            automation_id=name,
            repo=config.repo,
            task_type="cron",
            id=str(int(occurrence.timestamp())),
        )
        if not preview and self._emitted == identity.key:
            return []
        if not preview:
            self._emitted = identity.key
        return [
            Task(
                identity=identity,
                automation=self.automation,
                title=name,
                url=f"cron://{name}",
                scheduled_for=occurrence,
            )
        ]

    async def stream(self) -> AsyncIterator[Task]:
        """Yield pending runs and check the clock at the global cron interval."""
        while True:
            for task in await self.poll():
                yield task
            await self._sleep(self._polling.cron_poll_interval_seconds)


def latest_due_occurrence(
    config: CronAutomationConfiguration,
    state: CronRunState,
    now: datetime,
) -> datetime | None:
    """Find the latest due occurrence within an inclusive local-time window."""
    timezone = ZoneInfo(config.timezone or "UTC")
    start = config.start_date or state.created_at.astimezone(timezone)
    first = (
        start
        if croniter.match(config.schedule, start)
        else croniter(config.schedule, start).get_next(datetime)
    )
    ceiling = (
        min(now.astimezone(timezone), config.end_date)
        if config.end_date is not None
        else now.astimezone(timezone)
    )
    if ceiling < first:
        return None
    latest = croniter(config.schedule, ceiling + timedelta(microseconds=1)).get_prev(datetime)
    if latest < first or (
        state.last_scheduled_for is not None and latest <= state.last_scheduled_for
    ):
        return None
    return latest.astimezone(UTC)


class CronTrigger(Trigger):
    """Trigger implementation for locally scheduled cron automations."""

    trigger_type = "cron"
    configuration_type = CronAutomationConfiguration

    @classmethod
    def prompt_fields(cls) -> frozenset[str]:
        """Cron provides no trigger-specific prompt placeholders."""
        return frozenset()

    def prompt_context(self, task: Task) -> dict[str, str]:
        """Cron provides no trigger-specific prompt context."""
        return {}

    def build_feed(
        self, automation: ResolvedAutomation, dependencies: FeedDependencies
    ) -> TaskFeed:
        """Build the persistent local cron feed."""
        return CronTaskFeed(automation, dependencies.polling, dependencies.cron)


register(CronTrigger())
