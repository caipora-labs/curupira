"""GitHub task validation against current fake source state."""

from pathlib import Path

from curupira.models import GhIssue, GhPullRequest
from curupira.models.items import IssueItem
from curupira.tasks.revalidation import GitHubTaskRevalidator
from tests.fakes import FakeGitHub
from tests.helpers import issue_task, pull_request_task


async def test_issue_with_open_closing_pr_is_not_eligible(tmp_path: Path) -> None:
    task = issue_task(tmp_path)
    github = FakeGitHub(
        issues=[
            GhIssue(
                number=42,
                title="Current issue",
                url="https://github.com/acme/api/issues/42",
                state="OPEN",
            )
        ],
        pulls=[
            GhPullRequest(
                number=12,
                title="Implements issue",
                body="Fixes #42",
                url="https://github.com/acme/api/pull/12",
                state="OPEN",
            )
        ],
    )

    assert await GitHubTaskRevalidator(github)(task) is None


async def test_closed_issue_is_not_eligible_even_when_it_matches_old_snapshot(
    tmp_path: Path,
) -> None:
    task = issue_task(tmp_path)
    github = FakeGitHub(
        issues=[
            GhIssue(
                number=42,
                title=task.title,
                url=task.url,
                state="CLOSED",
            )
        ]
    )

    assert await GitHubTaskRevalidator(github)(task) is None


async def test_open_issue_without_closing_pr_is_refreshed(tmp_path: Path) -> None:
    task = issue_task(tmp_path)
    github = FakeGitHub(
        issues=[
            GhIssue(
                number=42,
                title="Updated title",
                body="New body",
                url="https://github.com/acme/api/issues/42",
                state="OPEN",
            )
        ]
    )

    refreshed = await GitHubTaskRevalidator(github)(task)

    assert refreshed is not None
    assert refreshed.title == "Updated title"
    assert isinstance(refreshed.item, IssueItem)
    assert refreshed.item.issue_body == "New body"


async def test_merged_pull_request_is_not_eligible(tmp_path: Path) -> None:
    task = pull_request_task(tmp_path, 12)
    github = FakeGitHub(
        pulls=[
            GhPullRequest(
                number=12,
                title="Review",
                url="https://github.com/acme/api/pull/12",
                state="CLOSED",
                mergedAt="2026-10-10T12:00:00Z",
            )
        ]
    )

    assert await GitHubTaskRevalidator(github)(task) is None


async def test_completion_next_action_for_still_open_work(tmp_path: Path) -> None:
    issue = issue_task(tmp_path)
    pull = pull_request_task(tmp_path, 12)
    github = FakeGitHub(
        issues=[
            GhIssue(
                number=42,
                title=issue.title,
                url=issue.url,
                state="OPEN",
            )
        ],
        pulls=[
            GhPullRequest(
                number=12,
                title="Review",
                url="https://github.com/acme/api/pull/12",
                state="OPEN",
                headRefOid="abc",
            )
        ],
    )
    revalidator = GitHubTaskRevalidator(github)

    assert await revalidator.completion_next_action(issue) == (
        "Create one draft pull request with a closing reference to this issue."
    )
    assert await revalidator.completion_next_action(pull) == (
        "Recheck remote checks, review, and merge status on this pull request."
    )
