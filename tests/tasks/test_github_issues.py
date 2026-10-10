"""GitHub issue task source and trigger behavior."""

from pathlib import Path

import pytest
from typing_extensions import override

from curupira.clients.gh import GhClient
from curupira.models import GhIssue, GhIssueSearchRequest, PollingSettings
from curupira.models.items import IssueItem
from curupira.storage import CronScheduleRepository
from curupira.tasks.base import FeedDependencies
from curupira.tasks.feed import PollingTaskFeed
from curupira.tasks.github_issues import GitHubIssueSource, IssueTrigger
from curupira.tasks.registry import get
from tests.helpers import issue_task, resolved_automation


class FakeGhClient(GhClient):
    """Return controlled issues and retain the search request for assertions."""

    def __init__(self, issues: list[GhIssue]) -> None:
        super().__init__()
        self.issues = issues
        self.request: GhIssueSearchRequest | None = None

    @override
    async def list_issues(self, request: GhIssueSearchRequest) -> list[GhIssue]:
        self.request = request
        return self.issues


@pytest.mark.asyncio
async def test_source_searches_issues_and_builds_tasks(tmp_path: Path) -> None:
    gh = FakeGhClient(
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

    tasks = await GitHubIssueSource(gh).discover(automation, 7)

    assert gh.request == GhIssueSearchRequest(repo="acme/api", query="is:open", limit=7)
    assert len(tasks) == 1
    assert tasks[0].identity.id == "42"
    assert tasks[0].identity.task_type == "issue"
    assert tasks[0].title == "Improve discovery"
    assert tasks[0].url == "https://github.com/acme/api/issues/42"
    assert tasks[0].item == IssueItem(
        issue_number="42",
        issue_title="Improve discovery",
        issue_body="Details",
        issue_url="https://github.com/acme/api/issues/42",
    )


def test_issue_trigger_is_registered_and_provides_prompt_context(tmp_path: Path) -> None:
    trigger = get("issue")
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
