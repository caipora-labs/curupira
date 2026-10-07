"""Bounded concurrent scheduling with exclusive execution per checkout."""

import asyncio
import logging
from collections import deque
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Sequence
from pathlib import Path

from curupira.executor import TaskExecutor
from curupira.models import ExecutionSettings, ProcessResult, RunningCodingSession, Task

logger = logging.getLogger(__name__)
WorkItem = tuple[Task, RunningCodingSession | None]
ActiveTasks = dict[asyncio.Task[ProcessResult], Task]
ReaderTask = asyncio.Task[WorkItem | None]


class TaskScheduler:
    """Run independent workspaces concurrently without concurrent checkout writers."""

    def __init__(
        self,
        settings: ExecutionSettings,
        executor: TaskExecutor,
        *,
        on_active_tasks_changed: Callable[[Sequence[Task]], None] | None = None,
    ) -> None:
        self._settings = settings
        self._executor = executor
        self._on_active_tasks_changed = on_active_tasks_changed
        self.failed_tasks = 0

    async def run(
        self, tasks: AsyncIterator[Task], *, resume_sessions: Sequence[RunningCodingSession] = ()
    ) -> None:
        """Consume bounded pending work while observing running tasks and discovery."""
        pending: deque[WorkItem] = deque()
        active: ActiveTasks = {}
        seen: set[str] = set()
        reader: ReaderTask | None = None

        async def incoming() -> AsyncGenerator[WorkItem, None]:
            try:
                for session in resume_sessions:
                    yield session.task, session
                async for selected in tasks:
                    yield selected, None
            finally:
                if isinstance(tasks, AsyncGenerator):
                    await tasks.aclose()

        source = incoming()
        exhausted = False
        try:
            self._notify_active_tasks(active)
            while not exhausted or pending or active:
                self._launch_available(pending, active)
                reader = self._ensure_reader(reader, exhausted, pending, source)
                waiting: set[asyncio.Task[object]] = set(active)
                if reader is not None:
                    waiting.add(reader)
                if not waiting:
                    break
                finished, _ = await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED)
                if reader is not None and reader in finished:
                    exhausted = self._consume_reader(reader, pending, seen)
                    reader = None
                self._reap_finished(active, finished, seen)
                self._notify_active_tasks(active)
        finally:
            await self._cancel_all(reader, active, source)

    def _launch_available(self, pending: deque[WorkItem], active: ActiveTasks) -> None:
        """Start pending tasks while concurrency and checkout exclusivity allow it."""
        occupied: set[Path] = {item.automation.workspace_path for item in active.values()}
        for _ in range(len(pending)):
            selected, resumed = pending.popleft()
            path = selected.automation.workspace_path
            if selected.automation.configuration.checkout == "worktree":
                path = path.with_name(f"{path.name}.worktrees") / selected.identity.key
            if len(active) >= self._settings.max_active_tasks or path in occupied:
                pending.append((selected, resumed))
                continue
            worker = asyncio.create_task(
                self._executor.execute(selected, resumed), name=selected.identity.key
            )
            active[worker] = selected
            occupied.add(path)
            self._notify_active_tasks(active)

    def _notify_active_tasks(self, active: ActiveTasks) -> None:
        """Publish active task snapshots for terminal status rendering."""
        if self._on_active_tasks_changed is not None:
            self._on_active_tasks_changed(tuple(active.values()))

    def _ensure_reader(
        self,
        reader: ReaderTask | None,
        exhausted: bool,
        pending: deque[WorkItem],
        source: AsyncGenerator[WorkItem, None],
    ) -> ReaderTask | None:
        """Read the next work item in the background until the stream is bounded or exhausted."""
        if reader is None and not exhausted and len(pending) < self._settings.max_pending_tasks:
            return asyncio.create_task(anext(source, None))
        return reader

    @staticmethod
    def _consume_reader(reader: ReaderTask, pending: deque[WorkItem], seen: set[str]) -> bool:
        """Admit a discovered item unless its identity is already tracked; report exhaustion."""
        item = reader.result()
        if item is None:
            return True
        key = item[0].identity.key
        if key not in seen:
            seen.add(key)
            pending.append(item)
        return False

    def _reap_finished(
        self, active: ActiveTasks, finished: set[asyncio.Task[object]], seen: set[str]
    ) -> None:
        """Account for completed workers and release cron keys for re-scheduling."""
        for worker in list(active):
            if worker not in finished:
                continue
            selected = active.pop(worker)
            self._record_outcome(selected, worker)
            if selected.identity.task_type == "cron":
                seen.discard(selected.identity.key)

    def _record_outcome(self, selected: Task, worker: asyncio.Task[ProcessResult]) -> None:
        """Count and log a completed task that exited unsuccessfully."""
        try:
            result = worker.result()
            if result.returncode != 0:
                self.failed_tasks += 1
                logger.error(
                    "Task %s failed with exit %s", selected.identity.key, result.returncode
                )
        except Exception:
            self.failed_tasks += 1
            logger.exception("Task %s failed", selected.identity.key)

    @staticmethod
    async def _cancel_all(
        reader: ReaderTask | None, active: ActiveTasks, source: AsyncGenerator[WorkItem, None]
    ) -> None:
        """Cancel outstanding work and close the input stream."""
        if reader is not None:
            reader.cancel()
            await asyncio.gather(reader, return_exceptions=True)
        for worker in active:
            worker.cancel()
        await asyncio.gather(*active, return_exceptions=True)
        await source.aclose()
