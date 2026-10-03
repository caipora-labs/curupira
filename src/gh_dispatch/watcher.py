"""Async generator that polls configured repositories for new issues."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from pathlib import Path

from gh_dispatch.clients.gh import GhClient
from gh_dispatch.errors import DispatchError
from gh_dispatch.models import (
    GhIssueSearchRequest,
    GhPullRequestSearchRequest,
    RepositoryWatcherSettings,
    SelectedTask,
)

logger = logging.getLogger(__name__)
MAX_POLL_INTERVAL_SECONDS = 5 * 60


class IssueWatcher:
    """Poll repositories sequentially and yield each issue once per process."""

    def __init__(
        self,
        settings: RepositoryWatcherSettings,
        gh: GhClient,
        workspace_dir: Path,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._settings = settings
        self._gh = gh
        self._workspace_dir = workspace_dir
        self._sleep = sleep
        self._seen: set[str] = set()

    async def watch(self) -> AsyncIterator[SelectedTask]:
        """Yield fresh issues in repository order; sleep only after an empty cycle."""
        base_interval = min(
            self._settings.poll_interval_seconds,
            MAX_POLL_INTERVAL_SECONDS,
        )
        poll_interval = base_interval

        while True:
            discovered: list[SelectedTask] = []

            for repository in self._settings.repositories:
                try:
                    issues = await self._gh.list_issues(
                        GhIssueSearchRequest(
                            repo=repository.repo,
                            query=repository.query,
                            limit=self._settings.batch_size,
                        )
                    )
                except DispatchError as error:
                    logger.warning("Could not check issues in %s: %s", repository.repo, error)
                    continue
                for issue in issues:
                    key = f"{repository.repo}#{issue.number}"
                    if key in self._seen:
                        continue
                    self._seen.add(key)
                    discovered.append(
                        SelectedTask(
                            task_type="issue",
                            repository=repository,
                            number=issue.number,
                            title=issue.title,
                            body=issue.body,
                            url=issue.url,
                            workspace_path=repository.workspace_path(self._workspace_dir),
                        )
                    )

            if not discovered:
                await self._sleep(poll_interval)
                poll_interval = min(poll_interval * 2, MAX_POLL_INTERVAL_SECONDS)
                continue

            poll_interval = base_interval
            for selected in discovered:
                yield selected


class PullRequestWatcher:
    """Poll configured repositories sequentially and yield fresh pull requests."""

    def __init__(
        self,
        settings: RepositoryWatcherSettings,
        gh: GhClient,
        workspace_dir: Path,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._settings = settings
        self._gh = gh
        self._workspace_dir = workspace_dir
        self._sleep = sleep
        self._seen: set[str] = set()

    async def watch(self) -> AsyncIterator[SelectedTask]:
        base_interval = min(self._settings.poll_interval_seconds, MAX_POLL_INTERVAL_SECONDS)
        poll_interval = base_interval

        while True:
            discovered: list[SelectedTask] = []
            for repository in self._settings.repositories:
                try:
                    pull_requests = await self._gh.list_pull_requests(
                        GhPullRequestSearchRequest(
                            repo=repository.repo,
                            query=repository.query,
                            limit=self._settings.batch_size,
                        )
                    )
                except DispatchError as error:
                    logger.warning(
                        "Could not check pull requests in %s: %s", repository.repo, error
                    )
                    continue

                for pull_request in pull_requests:
                    key = f"{repository.repo}#{pull_request.number}"
                    if key in self._seen:
                        continue
                    self._seen.add(key)
                    discovered.append(
                        SelectedTask(
                            task_type="pull_request",
                            repository=repository,
                            number=pull_request.number,
                            title=pull_request.title,
                            body=pull_request.body,
                            url=pull_request.url,
                            workspace_path=repository.workspace_path(self._workspace_dir),
                            is_draft=pull_request.is_draft,
                            head_ref_name=pull_request.head_ref_name,
                            base_ref_name=pull_request.base_ref_name,
                        )
                    )

            if not discovered:
                await self._sleep(poll_interval)
                poll_interval = min(poll_interval * 2, MAX_POLL_INTERVAL_SECONDS)
                continue

            poll_interval = base_interval
            for selected in discovered:
                yield selected


async def merge_task_streams(
    streams: Sequence[AsyncIterator[SelectedTask]],
    *,
    max_pending: int,
) -> AsyncIterator[SelectedTask]:
    """Multiplex issue and pull-request watcher generators with backpressure."""
    queue: asyncio.Queue[tuple[SelectedTask | None, Exception | None, bool]] = asyncio.Queue(
        maxsize=max_pending
    )

    async def pump(stream: AsyncIterator[SelectedTask]) -> None:
        try:
            async for selected in stream:
                await queue.put((selected, None, False))
        except asyncio.CancelledError:
            raise
        except Exception as error:
            await queue.put((None, error, False))
        finally:
            await queue.put((None, None, True))

    tasks = [asyncio.create_task(pump(stream)) for stream in streams]
    remaining = len(tasks)
    try:
        while remaining:
            selected, error, finished = await queue.get()
            if finished:
                remaining -= 1
            elif error is not None:
                raise error
            elif selected is not None:
                yield selected
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
