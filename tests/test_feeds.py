"""Polling, identity, backpressure, and producer shutdown behavior."""

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from typing_extensions import override

from gh_dispatch.clients.gh import GhClient
from gh_dispatch.errors import DispatchError
from gh_dispatch.feeds import GitHubTaskFeed, GitHubTaskSource, merge_task_streams
from gh_dispatch.models import (
    GhIssue,
    GhIssueSearchRequest,
    GhPullRequest,
    GhPullRequestSearchRequest,
    PollingSettings,
    Task,
)
from tests.helpers import issue_task, resolved_automation


class FakeGitHub(GhClient):
    """A controlled source with typed request recording."""

    def __init__(self, responses: list[list[GhIssue]]) -> None:
        super().__init__()
        self.responses = responses
        self.requests: list[GhIssueSearchRequest] = []

    @override
    async def list_issues(self, request: GhIssueSearchRequest) -> list[GhIssue]:
        self.requests.append(request)
        return self.responses.pop(0) if self.responses else []

    @override
    async def list_pull_requests(self, request: GhPullRequestSearchRequest) -> list[GhPullRequest]:
        items = await self.list_issues(request)
        return [GhPullRequest.model_validate(item.model_dump()) for item in items]


class StopPollingError(Exception):
    """End a deterministic polling test after its expected waits."""


def item(number: int = 1) -> GhIssue:
    """Provide a GitHub boundary response."""
    return GhIssue(number=number, title="Work", url=f"https://github.com/acme/api/issues/{number}")


@pytest.mark.parametrize("trigger", ["issue", "pull_request"])
async def test_shared_polling_deduplicates_and_uses_global_batch(
    tmp_path: Path, trigger: str
) -> None:
    gh = FakeGitHub([[item()], [item()]])
    feed = GitHubTaskFeed(
        resolved_automation(tmp_path, trigger=trigger), PollingSettings(batch_size=8), GitHubTaskSource(gh)
    )
    first = await feed.poll()
    assert len(first) == 1
    assert first[0].identity.task_type == trigger
    assert await feed.poll() == []
    assert gh.requests[0].limit == 8


async def test_different_automations_can_discover_the_same_item(tmp_path: Path) -> None:
    gh = FakeGitHub([[item()], [item()]])
    source = GitHubTaskSource(gh)
    first = GitHubTaskFeed(resolved_automation(tmp_path, "first"), PollingSettings(), source)
    second = GitHubTaskFeed(resolved_automation(tmp_path, "second"), PollingSettings(), source)
    tasks = [*(await first.poll()), *(await second.poll())]
    assert len({task.identity.key for task in tasks}) == 2


async def test_empty_cycles_back_off_and_reset_after_discovery(tmp_path: Path) -> None:
    waits: list[float] = []

    async def sleep(delay: float) -> None:
        waits.append(delay)
        if len(waits) == 4:
            raise StopPollingError

    gh = FakeGitHub([[], [], [item()], []])
    feed = GitHubTaskFeed(
        resolved_automation(tmp_path), PollingSettings(poll_interval_seconds=17), GitHubTaskSource(gh), sleep=sleep
    )
    stream = feed.stream()
    assert (await anext(stream)).identity.number == 1
    with pytest.raises(StopPollingError):
        await anext(stream)
    assert waits == [17, 34, 17, 34]


async def test_backoff_is_bounded_and_transient_errors_do_not_stop_stream(tmp_path: Path) -> None:
    class FailingGitHub(FakeGitHub):
        @override
        async def list_issues(self, request: GhIssueSearchRequest) -> list[GhIssue]:
            raise DispatchError("temporary error")

    waits: list[float] = []

    async def sleep(delay: float) -> None:
        waits.append(delay)
        if len(waits) == 3:
            raise StopPollingError

    feed = GitHubTaskFeed(
        resolved_automation(tmp_path),
        PollingSettings(poll_interval_seconds=200),
        GitHubTaskSource(FailingGitHub([])),
        sleep=sleep,
    )
    with pytest.raises(StopPollingError):
        await anext(feed.stream())
    assert waits == [200, 300, 300]


async def test_merge_closes_producers_when_full_queue_is_cancelled(tmp_path: Path) -> None:
    closed = asyncio.Event()

    async def infinite() -> AsyncIterator[Task]:
        try:
            while True:
                yield issue_task(tmp_path)
        finally:
            closed.set()

    merged = merge_task_streams([infinite()], max_pending=1)
    await anext(merged)
    await asyncio.sleep(0)
    await asyncio.wait_for(merged.aclose(), timeout=1)
    assert closed.is_set()


async def test_merge_propagates_errors_and_drains_finite_streams(tmp_path: Path) -> None:
    async def finite() -> AsyncIterator[Task]:
        yield issue_task(tmp_path)

    async def broken() -> AsyncIterator[Task]:
        raise DispatchError("broken feed")
        yield issue_task(tmp_path)

    assert (
        len([task async for task in merge_task_streams([finite(), finite()], max_pending=1)]) == 2
    )
    with pytest.raises(DispatchError, match="broken feed"):
        async for _ in merge_task_streams([finite(), broken()], max_pending=1):
            pass
