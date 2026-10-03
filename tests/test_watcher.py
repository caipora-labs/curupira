from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from gh_dispatch.clients.gh import GhClient
from gh_dispatch.config import AppSettings
from gh_dispatch.models import (
    GhIssue,
    GhIssueSearchRequest,
    GhPullRequest,
    GhPullRequestSearchRequest,
    RepositorySettings,
    SelectedTask,
)
from gh_dispatch.watcher import IssueWatcher, PullRequestWatcher, merge_task_streams


class FakeGhClient(GhClient):
    def __init__(self, responses: Sequence[list[GhIssue]]) -> None:
        super().__init__()
        self.responses = list(responses)
        self.requests: list[GhIssueSearchRequest] = []

    async def list_issues(self, request: GhIssueSearchRequest) -> list[GhIssue]:
        self.requests.append(request)
        return self.responses.pop(0)


class EmptyGhClient(GhClient):
    def __init__(self) -> None:
        super().__init__()

    async def list_issues(self, request: GhIssueSearchRequest) -> list[GhIssue]:
        return []


class FakePullRequestGhClient(GhClient):
    def __init__(self, responses: Sequence[list[GhPullRequest]]) -> None:
        super().__init__()
        self.responses = list(responses)
        self.requests: list[GhPullRequestSearchRequest] = []

    async def list_pull_requests(self, request: GhPullRequestSearchRequest) -> list[GhPullRequest]:
        self.requests.append(request)
        return self.responses.pop(0)


class StopPolling(Exception):
    pass


def make_settings(tmp_path: Path) -> AppSettings:
    return AppSettings.model_validate(
        {
            "agent": {"prompt": "Fix ${issue_number}"},
            "watchers": {
                "issues": {
                    "poll_interval_seconds": 17,
                    "batch_size": 8,
                    "repositories": [
                        {
                            "repo": "acme/first",
                            "path": tmp_path,
                            "query": "is:open label:ready",
                        },
                        {
                            "repo": "acme/second",
                            "path": tmp_path,
                            "query": "is:open label:ready",
                        },
                    ],
                }
            },
        }
    )


def make_issue(number: int, title: str) -> GhIssue:
    return GhIssue(
        number=number,
        title=title,
        body="details",
        url=f"https://github.com/acme/example/issues/{number}",
        state="OPEN",
    )


@pytest.mark.asyncio
async def test_watcher_scans_repositories_sequentially_and_sleeps_after_empty_cycle(
    tmp_path: Path,
) -> None:
    first = make_issue(1, "First")
    second = make_issue(2, "Second")
    gh = FakeGhClient(
        [
            [first],
            [second],
            [],
            [],
        ]
    )
    sleeps: list[float] = []

    async def stop_after_empty_cycle(delay: float) -> None:
        sleeps.append(delay)
        raise StopPolling

    watcher = IssueWatcher(
        make_settings(tmp_path).watchers.issues,
        gh,
        workspace_dir=tmp_path / "workspaces",
        sleep=stop_after_empty_cycle,
    )
    stream = watcher.watch()

    first_selected = await anext(stream)
    second_selected = await anext(stream)
    with pytest.raises(StopPolling):
        await anext(stream)

    assert isinstance(first_selected, SelectedTask)
    assert [first_selected.repository.repo, second_selected.repository.repo] == [
        "acme/first",
        "acme/second",
    ]
    assert [request.repo for request in gh.requests] == [
        "acme/first",
        "acme/second",
        "acme/first",
        "acme/second",
    ]
    assert all(request.limit == 8 for request in gh.requests)
    assert sleeps == [17]


@pytest.mark.asyncio
async def test_polling_backoff_doubles_up_to_five_minutes(tmp_path: Path) -> None:
    sleeps: list[float] = []

    async def stop_after_backoff(delay: float) -> None:
        sleeps.append(delay)
        if len(sleeps) == 7:
            raise StopPolling

    watcher = IssueWatcher(
        make_settings(tmp_path).watchers.issues,
        EmptyGhClient(),
        workspace_dir=tmp_path / "workspaces",
        sleep=stop_after_backoff,
    )

    with pytest.raises(StopPolling):
        await anext(watcher.watch())

    assert sleeps == [17, 34, 68, 136, 272, 300, 300]


@pytest.mark.asyncio
async def test_polling_backoff_resets_after_finding_an_issue(tmp_path: Path) -> None:
    issue = make_issue(21, "New task")
    gh = FakeGhClient([[], [], [issue], [], [], []])
    sleeps: list[float] = []

    async def stop_on_second_empty_cycle(delay: float) -> None:
        sleeps.append(delay)
        if len(sleeps) == 2:
            raise StopPolling

    watcher = IssueWatcher(
        make_settings(tmp_path).watchers.issues,
        gh,
        workspace_dir=tmp_path / "workspaces",
        sleep=stop_on_second_empty_cycle,
    )
    stream = watcher.watch()

    selected = await anext(stream)
    assert selected.number == 21
    with pytest.raises(StopPolling):
        await anext(stream)

    assert sleeps == [17, 17]


@pytest.mark.asyncio
async def test_watcher_deduplicates_seen_issues_and_waits_only_when_none_are_new(
    tmp_path: Path,
) -> None:
    issue = make_issue(10, "Already seen")
    gh = FakeGhClient([[issue], [], [issue], []])
    sleeps: list[float] = []

    async def stop_after_empty_cycle(delay: float) -> None:
        sleeps.append(delay)
        raise StopPolling

    watcher = IssueWatcher(
        make_settings(tmp_path).watchers.issues,
        gh,
        workspace_dir=tmp_path / "workspaces",
        sleep=stop_after_empty_cycle,
    )
    stream = watcher.watch()

    selected = await anext(stream)
    assert selected.number == 10
    with pytest.raises(StopPolling):
        await anext(stream)

    assert sleeps == [17]


@pytest.mark.asyncio
async def test_watcher_yields_remote_repo_even_when_local_clone_is_absent(
    tmp_path: Path,
) -> None:
    settings = AppSettings.model_validate(
        {
            "core": {"workspace_dir": tmp_path / "workspace"},
            "agent": {"prompt": "Fix ${issue_number}"},
            "watchers": {
                "issues": {
                    "repositories": [
                        {
                            "repo": "acme/uncloned",
                            "query": "project:mariotaddeucci/5",
                        }
                    ]
                }
            },
        }
    )
    gh = FakeGhClient([[make_issue(42, "Found remotely")]])
    watcher = IssueWatcher(
        settings.watchers.issues,
        gh,
        workspace_dir=settings.core.workspace_dir,
    )

    selected = await anext(watcher.watch())

    assert selected.number == 42
    assert selected.workspace_path == tmp_path / "workspace" / "acme" / "uncloned"
    assert not selected.workspace_path.exists()


@pytest.mark.asyncio
async def test_pull_request_watcher_yields_pr_tasks_sequentially(tmp_path: Path) -> None:
    settings = AppSettings.model_validate(
        {
            "agent": {
                "prompt": "Handle ${task_type} ${task_number}",
                "pull_request_prompt": "Review ${pull_request_number}: ${pull_request_title}",
            },
            "watchers": {
                "issues": {
                    "repositories": [{"repo": "acme/issues", "query": "is:open label:ready"}]
                },
                "pull_requests": {
                    "poll_interval_seconds": 11,
                    "batch_size": 6,
                    "repositories": [
                        {"repo": "acme/first", "query": "is:open label:review"},
                        {"repo": "acme/second", "query": "is:open label:review"},
                    ],
                },
            },
        }
    )
    first_pr = GhPullRequest(
        number=3,
        title="First PR",
        body="Review me",
        url="https://github.com/acme/first/pull/3",
        state="OPEN",
        isDraft=True,
        headRefName="feature/a",
        baseRefName="main",
    )
    second_pr = GhPullRequest(
        number=8,
        title="Second PR",
        body="Another review",
        url="https://github.com/acme/second/pull/8",
        state="OPEN",
        isDraft=False,
        headRefName="feature/b",
        baseRefName="main",
    )
    gh = FakePullRequestGhClient([[first_pr], [second_pr], [], []])
    sleeps: list[float] = []
    pull_request_settings = settings.watchers.pull_requests
    assert pull_request_settings is not None

    async def stop_after_empty_cycle(delay: float) -> None:
        sleeps.append(delay)
        raise StopPolling

    watcher = PullRequestWatcher(
        pull_request_settings,
        gh,
        workspace_dir=settings.core.workspace_dir,
        sleep=stop_after_empty_cycle,
    )
    stream = watcher.watch()

    first = await anext(stream)
    second = await anext(stream)
    with pytest.raises(StopPolling):
        await anext(stream)

    assert [first.task_type, second.task_type] == ["pull_request", "pull_request"]
    assert [first.repository.repo, second.repository.repo] == ["acme/first", "acme/second"]
    assert first.number == 3 and first.is_draft is True
    assert first.head_ref_name == "feature/a"
    assert [request.repo for request in gh.requests] == [
        "acme/first",
        "acme/second",
        "acme/first",
        "acme/second",
    ]
    assert all(request.limit == 6 for request in gh.requests)
    assert sleeps == [11]
    assert gh.requests[0].query == "is:open label:review"


@pytest.mark.asyncio
async def test_merge_task_streams_multiplexes_issues_and_pull_requests(
    tmp_path: Path,
) -> None:
    repository = RepositorySettings(repo="acme/api", path=tmp_path, query="is:open")
    issue_task = SelectedTask(
        task_type="issue",
        repository=repository,
        number=1,
        title="Issue",
        url="https://github.com/acme/api/issues/1",
        workspace_path=tmp_path,
    )
    pull_request_task = SelectedTask(
        task_type="pull_request",
        repository=repository,
        number=2,
        title="Pull request",
        url="https://github.com/acme/api/pull/2",
        workspace_path=tmp_path,
    )

    async def one_task(task: SelectedTask):
        yield task

    merged = [
        task
        async for task in merge_task_streams(
            [one_task(issue_task), one_task(pull_request_task)],
            max_pending=2,
        )
    ]

    assert {task.task_type for task in merged} == {"issue", "pull_request"}
