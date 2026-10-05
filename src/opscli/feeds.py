"""Shared GitHub polling and persistent cron task discovery."""

import asyncio
import logging
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

from croniter import croniter

from opscli.clients.gh import GhClient
from opscli.errors import DispatchError
from opscli.models import (
    CronAutomationConfiguration,
    CronRunState,
    GhIssueSearchRequest,
    GhPullRequest,
    GhPullRequestSearchRequest,
    PollingSettings,
    ResolvedAutomation,
    Task,
    TaskIdentity,
)
from opscli.storage import CronScheduleRepository

logger = logging.getLogger(__name__)
MAX_POLL_INTERVAL_SECONDS = 300.0


class TaskFeed(Protocol):
    """Discovery interface shared by one-shot dispatch and continuous polling."""

    async def poll(self, *, preview: bool = False) -> list[Task]:
        """Return tasks currently available; preview must not persist state."""
        ...

    def stream(self) -> AsyncIterator[Task]:
        """Yield new tasks continuously with source-appropriate waits."""
        ...


def utc_now() -> datetime:
    """Return an aware timestamp for injectable cron clocks."""
    return datetime.now(UTC)


class GitHubTaskFeed:
    """One issue or pull request automation with shared polling behavior."""

    def __init__(
        self,
        automation: ResolvedAutomation,
        polling: PollingSettings,
        gh: GhClient,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.automation = automation
        self._polling = polling
        self._gh = gh
        self._sleep = sleep
        self._seen: set[str] = set()

    async def poll(self, *, preview: bool = False) -> list[Task]:
        """Query the source and convert fresh items to automation-scoped tasks."""
        config = self.automation.configuration
        if isinstance(config, CronAutomationConfiguration):
            raise ValueError("GitHub feed cannot consume a cron configuration")
        if config.trigger_type == "issue":
            items = await self._gh.list_issues(
                GhIssueSearchRequest(
                    repo=config.repo, query=config.query, limit=self._polling.batch_size
                )
            )
        else:
            items = await self._gh.list_pull_requests(
                GhPullRequestSearchRequest(
                    repo=config.repo, query=config.query, limit=self._polling.batch_size
                )
            )
        tasks: list[Task] = []
        for item in items:
            identity = TaskIdentity(
                automation_id=self.automation.automation_id,
                repo=config.repo,
                task_type=config.trigger_type,
                number=item.number,
            )
            if identity.key in self._seen:
                continue
            if not preview:
                self._seen.add(identity.key)
            tasks.append(
                Task(
                    identity=identity,
                    automation=self.automation,
                    title=item.title,
                    body=item.body,
                    url=item.url,
                    is_draft=item.is_draft if isinstance(item, GhPullRequest) else None,
                    head_ref_name=item.head_ref_name if isinstance(item, GhPullRequest) else None,
                    base_ref_name=item.base_ref_name if isinstance(item, GhPullRequest) else None,
                )
            )
        return tasks

    async def stream(self) -> AsyncIterator[Task]:
        """Back off empty/error cycles and reset the interval after discovery."""
        base = min(self._polling.poll_interval_seconds, MAX_POLL_INTERVAL_SECONDS)
        interval = base
        while True:
            try:
                discovered: list[Task] = await self.poll()
            except DispatchError as error:
                logger.warning("Discovery failed for %s: %s", self.automation.automation_id, error)
                discovered = []
            if not discovered:
                await self._sleep(interval)
                interval = min(interval * 2, MAX_POLL_INTERVAL_SECONDS)
                continue
            interval = base
            for task in discovered:
                yield task


class CronTaskFeed:
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
            number=int(occurrence.timestamp()),
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


async def merge_task_streams(
    streams: Sequence[AsyncIterator[Task]],
    *,
    max_pending: int,
) -> AsyncGenerator[Task, None]:
    """Multiplex streams with bounded buffering and cancellation-safe completion."""
    if max_pending < 1:
        raise ValueError("max_pending must be positive")
    queue: asyncio.Queue[Task | Exception | None] = asyncio.Queue(maxsize=max_pending)

    async def pump(stream: AsyncIterator[Task]) -> None:
        try:
            async for task in stream:
                await queue.put(task)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            await queue.put(error)
        else:
            await queue.put(None)
        finally:
            close = getattr(stream, "aclose", None)
            if close is not None:
                await close()

    producers = [asyncio.create_task(pump(stream)) for stream in streams]
    remaining = len(producers)
    try:
        while remaining:
            value = await queue.get()
            if value is None:
                remaining -= 1
            elif isinstance(value, Exception):
                raise value
            else:
                yield value
    finally:
        for producer in producers:
            producer.cancel()
        await asyncio.gather(*producers, return_exceptions=True)
