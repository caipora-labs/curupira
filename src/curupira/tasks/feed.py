"""Source-agnostic polling and multiplexing for remote task feeds."""

import asyncio
import logging
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Sequence

from curupira.errors import DispatchError
from curupira.models import PollingSettings, ResolvedAutomation, Task
from curupira.tasks.base import TaskFeed, TaskSource

logger = logging.getLogger(__name__)
MAX_POLL_INTERVAL_SECONDS = 300.0


class PollingTaskFeed(TaskFeed):
    """Poll a generic task source with per-feed deduplication and bounded backoff."""

    def __init__(
        self,
        automation: ResolvedAutomation,
        polling: PollingSettings,
        source: TaskSource,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.automation = automation
        self._polling = polling
        self._source = source
        self._sleep = sleep
        self._seen: set[str] = set()

    async def poll(self, *, preview: bool = False) -> list[Task]:
        """Return unseen source tasks; preview leaves the deduplication set unchanged."""
        discovered = await self._source.discover(self.automation, self._polling.batch_size)
        tasks: list[Task] = []
        for task in discovered:
            identity = task.identity
            if identity.key in self._seen:
                continue
            if not preview:
                self._seen.add(identity.key)
            tasks.append(task)
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
