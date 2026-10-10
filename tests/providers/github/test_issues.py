"""GitHub issue task source and trigger behavior."""

from pathlib import Path

import pytest
from typing_extensions import override

from curupira.clients.github_graphql import GitHubGraphQLClient
from curupira.models import GhIssue, GitHubSearchRequest, PollingSettings
from curupira.models.configuration import IssueAutomationConfiguration
from curupira.models.items import IssueItem
from curupira.providers.github import GitHubIssueSource, IssueTrigger
from curupira.storage import CronScheduleRepository
from curupira.tasks.base import FeedDependencies
from curupira.tasks.feed import PollingTaskFeed
from curupira.tasks.registry import get
from tests.helpers import issue_task, resolved_automation


class FakeGitHubClient(GitHubGraphQLClient):
    """Return controlled issues and retain the search request for assertions."""

    def __init__(self, issues: list[GhIssue]) -> None:
        super().__init__()
        self.issues = issues
        self.request: GitHubSearchRequest | None = None

    @override
    async def list_issues(
        self,
        request: GitHubSearchRequest,
        *,
        configuration: IssueAutomationConfiguration | None = None,
    ) -> list[GhIssue]:
        del configuration
        self.request = request
        return self.issues


@pytest.mark.asyncio
async def test_source_searches_issues_and_builds_tasks(tmp_path: Path) -> None:
    client = FakeGitHubClient(
        [
            GhIssue(
                number=42,
                title="Improve discovery",
                body="Details",
                url="https://github.com/acme/api/issues/42",
            )
        ]
    )
    automation = resolved_automation(tmp_path)

    tasks = await GitHubIssueSource(client).discover(automation, 7)

    assert client.request is not None
    assert client.request.repo == "acme/api"
    assert client.request.limit == 7
    assert "repo:acme/api" in client.request.query
    assert "is:issue" in client.request.query
    assert "label:agent-ready" in client.request.query
    assert len(tasks) == 1
    assert tasks[0].identity.id == "42"
    assert tasks[0].identity.task_type == "github-issues"
    assert tasks[0].title == "Improve discovery"
    assert tasks[0].url == "https://github.com/acme/api/issues/42"
    assert tasks[0].item == IssueItem(
        issue_number="42",
        issue_title="Improve discovery",
        issue_body="Details",
        issue_url="https://github.com/acme/api/issues/42",
    )


def test_issue_trigger_is_registered_and_provides_prompt_context(tmp_path: Path) -> None:
    trigger = get("github-issues")
    task = issue_task(tmp_path, number=54)

    assert isinstance(trigger, IssueTrigger)
    assert trigger.prompt_fields() == frozenset(
        {"issue_number", "issue_title", "issue_body", "issue_url"}
    )
    assert trigger.prompt_context(task) == {
        "issue_number": "54",
        "issue_title": "Task 54",
        "issue_body": "Details",
        "issue_url": "https://github.com/acme/api/issues/54",
    }


def test_issue_trigger_builds_polling_feed(tmp_path: Path) -> None:
    automation = resolved_automation(tmp_path)

    feed = IssueTrigger().build_feed(
        automation,
        FeedDependencies(
            polling=PollingSettings(),
            cron=CronScheduleRepository(tmp_path / "state.sqlite3"),
            state_db_path=tmp_path / "state.sqlite3",
        ),
    )

    assert isinstance(feed, PollingTaskFeed)
    assert feed.automation is automation
