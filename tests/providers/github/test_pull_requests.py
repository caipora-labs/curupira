"""GitHub pull-request task source and trigger behavior."""

from pathlib import Path

import pytest
from typing_extensions import override

from curupira.clients.github_graphql import GitHubGraphQLClient
from curupira.models import GhPullRequest, GitHubSearchRequest, PollingSettings
from curupira.models.configuration import PullRequestAutomationConfiguration
from curupira.models.items import PullRequestItem
from curupira.providers.github import GitHubPullRequestSource, PullRequestTrigger
from curupira.storage import CronScheduleRepository
from curupira.tasks.base import FeedDependencies
from curupira.tasks.feed import PollingTaskFeed
from curupira.tasks.registry import get
from tests.helpers import pull_request_task, resolved_automation


class FakeGitHubClient(GitHubGraphQLClient):
    """Return controlled pull requests and retain the search request."""

    def __init__(self, pull_requests: list[GhPullRequest]) -> None:
        super().__init__()
        self.pull_requests = pull_requests
        self.request: GitHubSearchRequest | None = None
        self.configuration: PullRequestAutomationConfiguration | None = None

    @override
    async def list_pull_requests(
        self,
        request: GitHubSearchRequest,
        *,
        configuration: PullRequestAutomationConfiguration | None = None,
    ) -> list[GhPullRequest]:
        self.request = request
        self.configuration = configuration
        return self.pull_requests


@pytest.mark.asyncio
async def test_source_searches_pull_requests_and_builds_tasks(tmp_path: Path) -> None:
    client = FakeGitHubClient(
        [
            GhPullRequest(
                number=42,
                title="Review change",
                body="Details",
                url="https://github.com/acme/api/pull/42",
                isDraft=True,
                headRefName="feature",
                baseRefName="main",
            )
        ]
    )
    automation = resolved_automation(
        tmp_path,
        "reviews",
        "github-pull-requests",
        mergeable=True,
        draft=False,
    )

    tasks = await GitHubPullRequestSource(client).discover(automation, 7)

    assert client.request is not None
    assert client.request.repo == "acme/api"
    assert client.request.limit == 7
    assert "is:pr" in client.request.query
    assert "draft:false" in client.request.query
    assert client.configuration is not None
    assert client.configuration.mergeable is True
    assert len(tasks) == 1
    assert tasks[0].identity.id == "42"
    assert tasks[0].identity.task_type == "github-pull-requests"
    assert tasks[0].title == "Review change"
    assert tasks[0].url == "https://github.com/acme/api/pull/42"
    assert tasks[0].item == PullRequestItem(
        pull_request_number="42",
        pull_request_title="Review change",
        pull_request_body="Details",
        pull_request_url="https://github.com/acme/api/pull/42",
        pull_request_is_draft=True,
        pull_request_head_ref="feature",
        pull_request_base_ref="main",
    )


def test_pull_request_trigger_is_registered_and_provides_prompt_context(tmp_path: Path) -> None:
    trigger = get("github-pull-requests")
    assert trigger.trigger_type == "github-pull-requests"
    task = pull_request_task(tmp_path, number=54)

    assert isinstance(trigger, PullRequestTrigger)
    assert trigger.prompt_fields() == frozenset(
        {
            "pull_request_number",
            "pull_request_title",
            "pull_request_body",
            "pull_request_url",
            "pull_request_is_draft",
            "pull_request_head_ref",
            "pull_request_base_ref",
            "pull_request_head_sha",
            "pull_request_mergeable",
            "pull_request_merge_state_status",
            "pull_request_check_conclusions",
            "pull_request_linked_issue_numbers",
            "pull_request_linked_issue_states",
        }
    )
    assert trigger.prompt_context(task) == {
        "pull_request_number": "54",
        "pull_request_title": "Review",
        "pull_request_body": "",
        "pull_request_url": "https://github.com/acme/api/pull/54",
        "pull_request_is_draft": "true",
        "pull_request_head_ref": "feature",
        "pull_request_base_ref": "main",
        "pull_request_head_sha": "head-default",
        "pull_request_mergeable": "",
        "pull_request_merge_state_status": "",
        "pull_request_check_conclusions": "[]",
        "pull_request_linked_issue_numbers": "[]",
        "pull_request_linked_issue_states": "[]",
    }


def test_pull_request_trigger_builds_polling_feed(tmp_path: Path) -> None:
    automation = resolved_automation(tmp_path, "reviews", "github-pull-requests")

    feed = PullRequestTrigger().build_feed(
        automation,
        FeedDependencies(
            polling=PollingSettings(),
            cron=CronScheduleRepository(tmp_path / "state.sqlite3"),
            state_db_path=tmp_path / "state.sqlite3",
        ),
    )

    assert isinstance(feed, PollingTaskFeed)
    assert feed.automation is automation
