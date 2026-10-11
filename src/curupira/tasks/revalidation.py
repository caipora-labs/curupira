"""Current GitHub-state checks for discovered and recovered work items."""

import re
from collections.abc import Awaitable, Callable

from curupira.clients.github_graphql import GitHubGraphQLClient
from curupira.models import GhIssue, GhPullRequest, GhTaskViewRequest, Task
from curupira.models.items import IssueItem, PullRequestItem

TaskValidator = Callable[[Task], Awaitable[Task | None]]
_CLOSING_REFERENCE = re.compile(
    r"\b(?:clos(?:e|es|ed)|fix(?:es|ed)?|resolv(?:e|es|ed))\s+"
    r"(?:(?P<repo>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+))?#(?P<number>\d+)\b",
    flags=re.IGNORECASE,
)


class GitHubTaskRevalidator:
    """Refresh GitHub work before dispatch and derive an explicit next action."""

    def __init__(self, gh: GitHubGraphQLClient) -> None:
        self._gh = gh

    async def __call__(self, task: Task) -> Task | None:
        """Return a refreshed open task, or ``None`` when it left its workflow queue."""
        if task.identity.task_type == "github-issues":
            return await self._revalidate_issue(task)
        if task.identity.task_type == "github-pull-requests":
            return await self._revalidate_pull_request(task)
        return task

    async def completion_next_action(self, task: Task) -> str | None:
        """Return the explicit external follow-up when source work is still incomplete."""
        current = await self(task)
        if current is None:
            return None
        if task.identity.task_type == "github-issues":
            return "Create one draft pull request with a closing reference to this issue."
        if task.identity.task_type == "github-pull-requests":
            return "Recheck remote checks, review, and merge status on this pull request."
        return None

    async def _revalidate_issue(self, task: Task) -> Task | None:
        issue = await self._gh.view_issue(_view_request(task))
        if _state(issue.state) != "OPEN":
            return None
        pulls = await self._gh.list_pull_requests_for_issue(
            task.identity.repo, int(task.identity.id)
        )
        if any(_closes_issue(pull, task.identity.repo, int(task.identity.id)) for pull in pulls):
            return None
        return task.model_copy(update=_issue_task_fields(issue))

    async def _revalidate_pull_request(self, task: Task) -> Task | None:
        pull = await self._gh.view_pull_request(_view_request(task))
        if _state(pull.state) != "OPEN" or pull.merged_at is not None:
            return None
        linked_numbers: list[str] = []
        linked_states: list[str] = []
        for reference in pull.closing_issues_references:
            linked_repo = reference.repository.name_with_owner if reference.repository else None
            if linked_repo is not None and linked_repo.casefold() != task.identity.repo.casefold():
                continue
            issue = await self._gh.view_issue(
                GhTaskViewRequest(repo=task.identity.repo, number=reference.number)
            )
            linked_numbers.append(str(reference.number))
            linked_states.append(_state(issue.state))
        return task.model_copy(
            update=_pull_request_task_fields(pull, linked_numbers, linked_states)
        )


def _view_request(task: Task) -> GhTaskViewRequest:
    return GhTaskViewRequest(repo=task.identity.repo, number=int(task.identity.id))


def _issue_task_fields(issue: GhIssue) -> dict[str, object]:
    return {
        "title": issue.title,
        "url": issue.url,
        "item": IssueItem(
            issue_number=str(issue.number),
            issue_title=issue.title,
            issue_body=issue.body or "",
            issue_url=issue.url,
        ),
    }


def _pull_request_task_fields(
    pull: GhPullRequest, linked_numbers: list[str], linked_states: list[str]
) -> dict[str, object]:
    return {
        "title": pull.title,
        "url": pull.url,
        "item": PullRequestItem(
            pull_request_number=str(pull.number),
            pull_request_title=pull.title,
            pull_request_body=pull.body or "",
            pull_request_url=pull.url,
            pull_request_is_draft=pull.is_draft,
            pull_request_head_ref=pull.head_ref_name,
            pull_request_base_ref=pull.base_ref_name,
            pull_request_head_sha=pull.head_ref_oid,
            pull_request_mergeable=pull.mergeable,
            pull_request_merge_state_status=pull.merge_state_status,
            pull_request_check_conclusions=tuple(
                check.conclusion or check.state or "UNKNOWN" for check in pull.status_check_rollup
            ),
            pull_request_linked_issue_numbers=tuple(linked_numbers),
            pull_request_linked_issue_states=tuple(linked_states),
        ),
    }


def _state(value: str | None) -> str:
    return value.upper() if value is not None else "UNKNOWN"


def _closes_issue(pull: GhPullRequest, repo: str, issue_number: int) -> bool:
    for reference in pull.closing_issues_references:
        linked_repo = reference.repository.name_with_owner if reference.repository else None
        if reference.number == issue_number and (
            linked_repo is None or linked_repo.casefold() == repo.casefold()
        ):
            return True
    for match in _CLOSING_REFERENCE.finditer(pull.body or ""):
        linked_repo = match.group("repo")
        if int(match.group("number")) == issue_number and (
            linked_repo is None or linked_repo.casefold() == repo.casefold()
        ):
            return True
    return False
