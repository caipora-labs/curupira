"""Official GitHub issues / pull-requests triggers.

Discovery authenticates through `gh auth token`; no GitHub credentials are stored here.
"""

from __future__ import annotations

from typing import Any

from curupira_sdk import Curupira, RpcError
from pydantic import ValidationError

from curupira_plugins.github.client import Discovery, GitHubClient, GitHubCliToken, parse_nodes
from curupira_plugins.github.filters import IssueFilters, PullRequestFilters
from curupira_plugins.github.models import IssueItem, IssueNode, PullRequestItem, PullRequestNode

_CLIENT = GitHubClient(GitHubCliToken())
# One discovery feed per distinct filter set, kept for the lifetime of this process.
_FEEDS: dict[str, Discovery[Any, Any]] = {}


def _validation_message(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors()
    )


def _check_issue_filters(kwargs: dict[str, object]) -> None:
    try:
        IssueFilters(**kwargs)  # type: ignore[arg-type]
    except ValidationError as exc:
        raise RpcError(-32003, _validation_message(exc)) from exc


def _check_pull_request_filters(kwargs: dict[str, object]) -> None:
    try:
        PullRequestFilters(**kwargs)  # type: ignore[arg-type]
    except ValidationError as exc:
        raise RpcError(-32003, _validation_message(exc)) from exc


def _issue_item(repo: str, node: IssueNode) -> IssueItem:
    return IssueItem(
        id=str(node.number),
        title=node.title,
        url=node.url,
        repo=repo,
        issue_number=node.number,
        issue_title=node.title,
        issue_body=node.body or "",
        issue_url=node.url,
        issue_state=node.state,
        issue_author=node.author.login if node.author else "",
        issue_labels=[label.name for label in node.labels.nodes],
    )


def _pull_request_item(repo: str, node: PullRequestNode) -> PullRequestItem:
    return PullRequestItem(
        id=str(node.number),
        title=node.title,
        url=node.url,
        repo=repo,
        pull_request_number=node.number,
        pull_request_title=node.title,
        pull_request_body=node.body or "",
        pull_request_url=node.url,
        pull_request_is_draft=node.is_draft,
        pull_request_head_ref=node.head_ref_name,
        pull_request_base_ref=node.base_ref_name,
        pull_request_head_sha=node.head_ref_oid,
        pull_request_author=node.author.login if node.author else "",
        pull_request_labels=[label.name for label in node.labels.nodes],
        pull_request_mergeable=node.mergeable,
        pull_request_merge_state_status=node.merge_state_status,
    )


def _issue_feed(filters: IssueFilters) -> Discovery[IssueNode, IssueItem]:
    key = f"issue:{filters.model_dump_json()}"
    feed = _FEEDS.get(key)
    if feed is None:
        query = filters.search_query()
        feed = Discovery(
            fetch_page=lambda after: _CLIENT.search(query, after=after),
            parse_page=lambda connection: parse_nodes(connection, IssueNode),
            keep=lambda node: True,
            to_item=lambda node: _issue_item(filters.repo, node),
        )
        _FEEDS[key] = feed
    return feed


def _pull_request_feed(
    filters: PullRequestFilters,
) -> Discovery[PullRequestNode, PullRequestItem]:
    key = f"pull_request:{filters.model_dump_json()}"
    feed = _FEEDS.get(key)
    if feed is None:
        query = filters.search_query()
        feed = Discovery(
            fetch_page=lambda after: _CLIENT.search(query, after=after),
            parse_page=lambda connection: parse_nodes(connection, PullRequestNode),
            keep=lambda node: filters.keeps(
                mergeable_state=node.mergeable,
                merge_state_status=node.merge_state_status,
            ),
            to_item=lambda node: _pull_request_item(filters.repo, node),
        )
        _FEEDS[key] = feed
    return feed


def github_issues(
    repo: str,
    labels: list[str] | None = None,
    exclude_labels: list[str] | None = None,
    state: str = "open",
    assignee: str | None = None,
    author: str | None = None,
    milestone: str | None = None,
    project: str | None = None,
    linked_pull_request: bool | None = None,
    sort: str | None = None,
) -> IssueItem | None:
    """Return the next eligible GitHub issue, or None when none are available."""
    filters = IssueFilters(
        repo=repo,
        labels=labels,
        exclude_labels=exclude_labels,
        state=state,  # type: ignore[arg-type]
        assignee=assignee,
        author=author,
        milestone=milestone,
        project=project,
        linked_pull_request=linked_pull_request,
        sort=sort,  # type: ignore[arg-type]
    )
    return _issue_feed(filters).next_item()


def github_pull_requests(
    repo: str,
    labels: list[str] | None = None,
    exclude_labels: list[str] | None = None,
    state: str = "open",
    assignee: str | None = None,
    author: str | None = None,
    milestone: str | None = None,
    project: str | None = None,
    draft: bool | None = None,
    base: str | None = None,
    head: str | None = None,
    review: str | None = None,
    ci_status: str | None = None,
    linked_issue: bool | None = None,
    mergeable: bool | None = None,
    merge_state: list[str] | None = None,
    sort: str | None = None,
) -> PullRequestItem | None:
    """Return the next eligible GitHub pull request, or None when none are available."""
    filters = PullRequestFilters(
        repo=repo,
        labels=labels,
        exclude_labels=exclude_labels,
        state=state,  # type: ignore[arg-type]
        assignee=assignee,
        author=author,
        milestone=milestone,
        project=project,
        draft=draft,
        base=base,
        head=head,
        review=review,  # type: ignore[arg-type]
        ci_status=ci_status,  # type: ignore[arg-type]
        linked_issue=linked_issue,
        mergeable=mergeable,
        merge_state=merge_state,  # type: ignore[arg-type]
        sort=sort,  # type: ignore[arg-type]
    )
    return _pull_request_feed(filters).next_item()


def register(app: Curupira) -> None:
    """Register GitHub triggers on ``app``."""
    app.trigger(github_issues)
    app.trigger(github_pull_requests)
    app.param_check("github-issues", _check_issue_filters)
    app.param_check("github-pull-requests", _check_pull_request_filters)
