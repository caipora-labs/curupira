"""Bounded concurrent scheduling with exclusive execution per checkout."""

import asyncio
import logging
from collections import deque
from collections.abc import AsyncGenerator, AsyncIterator, Awaitable, Callable, Sequence
from pathlib import Path

from curupira.executor import TaskExecutor
from curupira.models import ExecutionSettings, ProcessResult, RunningCodingSession, Task
from curupira.storage import CompletedTaskRepository
from curupira.tasks.revalidation import TaskValidator

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
        task_validator: TaskValidator | None = None,
        completion_verifier: Callable[[Task], Awaitable[str | None]] | None = None,
        completed_tasks: CompletedTaskRepository | None = None,
    ) -> None:
        self._settings = settings
        self._executor = executor
        self._on_active_tasks_changed = on_active_tasks_changed
        self._task_validator = task_validator
        self._completion_verifier = completion_verifier
        self._completed_tasks = completed_tasks
        self._admit = asyncio.Event()
        self._admit.set()
        self._reload_requested = False
        self.failed_tasks = 0

    def pause(self) -> None:
        """Stop admitting newly discovered work until ``resume`` is called."""
        self._admit.clear()

    def resume(self) -> None:
        """Allow the scheduler to admit and launch work again."""
        if self._reload_requested:
            return
        self._admit.set()

    def request_reload(self) -> None:
        """Stop new admissions and exit once every in-flight task finishes."""
        self._reload_requested = True
        self.pause()

    @property
    def paused(self) -> bool:
        """Return whether new work admission is currently suspended."""
        return not self._admit.is_set()

    @property
    def reload_requested(self) -> bool:
        """Return whether the scheduler is draining for a configuration reload."""
        return self._reload_requested

    async def run(
        self,
        tasks: AsyncIterator[Task],
        *,
        resume_sessions: Sequence[RunningCodingSession] = (),
        initial_tasks: Sequence[Task] = (),
    ) -> None:
        """Consume bounded work while validating recovered and discovered snapshots."""
        pending: deque[WorkItem] = deque()
        for session in resume_sessions:
            pending.append((session.task, session))
        for task in initial_tasks:
            pending.append((task, None))
        active: ActiveTasks = {}
        seen: set[str] = set()
        reader: ReaderTask | None = None

        async def incoming() -> AsyncGenerator[WorkItem, None]:
            try:
                async for selected in tasks:
                    yield selected, None
            finally:
                if isinstance(tasks, AsyncGenerator):
                    await tasks.aclose()

        source = incoming()
        exhausted = False
        try:
            self._notify_active_tasks(active)
            while not self._should_exit(exhausted, pending, active):
                if self._reload_requested and not active:
                    pending.clear()
                    break
                reader, exhausted = await self._advance_admission(
                    reader, exhausted, pending, active, source, seen
                )
                waiting = self._waiting_tasks(active, reader)
                if not waiting:
                    if await self._wait_while_idle(exhausted, pending):
                        continue
                    break
                finished, _ = await asyncio.wait(waiting, return_when=asyncio.FIRST_COMPLETED)
                reader, exhausted = self._collect_reader(reader, finished, pending, seen, exhausted)
                await self._reap_finished(active, finished, seen)
                self._notify_active_tasks(active)
        finally:
            await self._cancel_all(reader, active, source)

    def _should_exit(self, exhausted: bool, pending: deque[WorkItem], active: ActiveTasks) -> bool:
        """Return whether the scheduler has no work left and is not paused."""
        return exhausted and not pending and not active and not self.paused

    async def _advance_admission(
        self,
        reader: ReaderTask | None,
        exhausted: bool,
        pending: deque[WorkItem],
        active: ActiveTasks,
        source: AsyncGenerator[WorkItem, None],
        seen: set[str],
    ) -> tuple[ReaderTask | None, bool]:
        """Launch work or cancel discovery while a reload drain is in progress."""
        if self._admit.is_set():
            await self._launch_available(pending, active, seen)
            return self._ensure_reader(reader, exhausted, pending, source), exhausted
        if self._reload_requested and reader is not None:
            await self._cancel_reader(reader)
            return None, exhausted
        return reader, exhausted

    @staticmethod
    def _waiting_tasks(active: ActiveTasks, reader: ReaderTask | None) -> set[asyncio.Task[object]]:
        """Collect active workers and the optional discovery reader."""
        waiting: set[asyncio.Task[object]] = set(active)
        if reader is not None:
            waiting.add(reader)
        return waiting

    async def _wait_while_idle(self, exhausted: bool, pending: deque[WorkItem]) -> bool:
        """Wait for resume when paused with leftover work; otherwise stop the loop."""
        if self.paused and not self._reload_requested and (not exhausted or pending):
            await self._admit.wait()
            return True
        return self._reload_requested

    def _collect_reader(
        self,
        reader: ReaderTask | None,
        finished: set[asyncio.Task[object]],
        pending: deque[WorkItem],
        seen: set[str],
        exhausted: bool,
    ) -> tuple[ReaderTask | None, bool]:
        """Consume a finished reader into pending work when it was not cancelled."""
        if reader is None or reader not in finished:
            return reader, exhausted
        if reader.cancelled():
            return None, exhausted
        return None, self._consume_reader(reader, pending, seen)

    async def _launch_available(
        self, pending: deque[WorkItem], active: ActiveTasks, seen: set[str]
    ) -> None:
        """Start pending tasks while concurrency and checkout exclusivity allow it."""
        occupied: set[Path] = {item.automation.workspace_path for item in active.values()}
        validated = await self._validate_pending(pending, seen)
        for selected, resumed in validated:
            path = selected.automation.workspace_path
            if selected.automation.configuration.checkout == "worktree":
                path = path.with_name(f"{path.name}.worktrees") / selected.identity.key
            if len(active) >= self._settings.max_active_tasks or path in occupied:
                pending.append((selected, resumed))
                continue
            seen.add(selected.dispatch_key)
            worker = asyncio.create_task(
                self._executor.execute(selected, resumed), name=selected.identity.key
            )
            active[worker] = selected
            occupied.add(path)
            self._notify_active_tasks(active)

    async def _validate_pending(self, pending: deque[WorkItem], seen: set[str]) -> list[WorkItem]:
        """Revalidate, retire stale sessions, and prepare one pending admission round."""
        candidates = list(pending)
        pending.clear()
        validated: list[WorkItem] = []
        for item in candidates:
            refreshed = await self._validate_candidate(item, seen)
            if refreshed is None:
                continue
            selected, resumed = refreshed
            key = selected.dispatch_key
            if key in seen:
                if resumed is not None:
                    await self._executor.discard_session(resumed.task)
                continue
            validated.append(refreshed)
        return validated

    async def _validate_candidate(self, item: WorkItem, seen: set[str]) -> WorkItem | None:
        """Refresh one candidate and retire any session or result for an outdated snapshot."""
        selected, resumed = item
        original = selected
        if self._task_validator is not None:
            selected = await self._task_validator(selected)
            if selected is None:
                if resumed is not None:
                    await self._executor.discard_session(resumed.task)
                if self._completed_tasks is not None:
                    await self._completed_tasks.delete(original)
                seen.add(original.dispatch_key)
                return None
        if resumed is not None:
            if resumed.task.state_fingerprint != selected.state_fingerprint:
                await self._executor.discard_session(resumed.task)
                resumed = None
            else:
                selected = resumed.task
        if self._completed_tasks is not None:
            completed = await self._completed_tasks.get(selected)
            if completed is not None:
                if completed.fingerprint == selected.state_fingerprint:
                    if resumed is not None:
                        await self._executor.discard_session(resumed.task)
                    logger.info(
                        "Skipping unchanged completed task %s; next action: %s",
                        selected.url,
                        completed.next_action,
                    )
                    seen.add(selected.dispatch_key)
                    return None
                await self._completed_tasks.delete(selected)
        return selected, resumed

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
        key = item[0].dispatch_key
        if key not in seen:
            pending.append(item)
        return False

    async def _reap_finished(
        self, active: ActiveTasks, finished: set[asyncio.Task[object]], seen: set[str]
    ) -> None:
        """Account for completed workers and release cron keys for re-scheduling."""
        for worker in list(active):
            if worker not in finished:
                continue
            selected = active.pop(worker)
            result = self._record_outcome(selected, worker)
            if (
                result is not None
                and result.returncode == 0
                and self._completion_verifier is not None
            ):
                try:
                    next_action = await self._completion_verifier(selected)
                except Exception as error:
                    self.failed_tasks += 1
                    next_action = (
                        "Retry GitHub state validation before dispatching this completed snapshot "
                        f"(verification error: {type(error).__name__})."
                    )
                    if self._completed_tasks is not None:
                        await self._completed_tasks.save(selected, next_action)
                    logger.error(
                        "Could not verify completion for %s; next action: %s",
                        selected.url,
                        next_action,
                    )
                else:
                    if next_action is None:
                        if self._completed_tasks is not None:
                            await self._completed_tasks.delete(selected)
                    else:
                        if self._completed_tasks is not None:
                            await self._completed_tasks.save(selected, next_action)
                        logger.info(
                            "Task %s remains incomplete; next action: %s", selected.url, next_action
                        )
            if selected.identity.task_type == "cron":
                seen.discard(selected.dispatch_key)

    def _record_outcome(
        self, selected: Task, worker: asyncio.Task[ProcessResult]
    ) -> ProcessResult | None:
        """Count and log a completed task that exited unsuccessfully."""
        try:
            result = worker.result()
            if result.returncode != 0:
                self.failed_tasks += 1
                logger.error(
                    "Task %s failed with exit %s", selected.identity.key, result.returncode
                )
            return result
        except Exception:
            self.failed_tasks += 1
            logger.exception("Task %s failed", selected.identity.key)
            return None

    @staticmethod
    async def _cancel_reader(reader: ReaderTask) -> None:
        """Cancel a background discovery reader and wait for it to settle."""
        reader.cancel()
        await asyncio.gather(reader, return_exceptions=True)

    @staticmethod
    async def _cancel_all(
        reader: ReaderTask | None, active: ActiveTasks, source: AsyncGenerator[WorkItem, None]
    ) -> None:
        """Cancel outstanding work and close the input stream."""
        if reader is not None:
            await TaskScheduler._cancel_reader(reader)
        for worker in active:
            worker.cancel()
        await asyncio.gather(*active, return_exceptions=True)
        await source.aclose()
