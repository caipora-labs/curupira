"""Official GitHub issues / pull-requests triggers.

Discovery authenticates through `gh auth token`; no GitHub credentials are stored here.
"""

from __future__ import annotations

import json
from typing import Any

from curupira_sdk import Curupira, RpcError
from pydantic import ValidationError

from curupira_plugins.github.client import Discovery, GitHubClient, GitHubCliToken, parse_nodes
from curupira_plugins.github.filters import IssueFilters, ProjectFilters, PullRequestFilters
from curupira_plugins.github.models import (
    IssueItem,
    IssueNode,
    ProjectItem,
    ProjectItemNode,
    PullRequestItem,
    PullRequestNode,
    ReferenceConnection,
)

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


def _reference_urls(references: ReferenceConnection) -> list[str]:
    return [reference.url for reference in references.nodes]


def _check_project_filters(kwargs: dict[str, object]) -> None:
    try:
        ProjectFilters(**kwargs)  # type: ignore[arg-type]
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
        issue_assignees=[actor.login for actor in node.assignees.nodes],
        issue_milestone=node.milestone.title if node.milestone else "",
        issue_created_at=node.created_at,
        issue_state_reason=node.state_reason or "",
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
        pull_request_assignees=[actor.login for actor in node.assignees.nodes],
        pull_request_milestone=node.milestone.title if node.milestone else "",
        pull_request_created_at=node.created_at,
        pull_request_changed_files=node.changed_files,
        pull_request_additions=node.additions,
        pull_request_deletions=node.deletions,
        pull_request_closing_issues=_reference_urls(node.closing_issues_references),
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


def _project_item(
    filters: ProjectFilters,
    project_title: str,
    project_url: str,
    node: ProjectItemNode,
) -> ProjectItem | None:
    """Map one project item to a task, or None when it is not an eligible issue/PR."""
    content = node.content or {}
    kind = content.get("__typename")
    if node.is_archived or kind not in {"Issue", "PullRequest"}:
        return None  # draft items, redacted content, and archived cards carry no repository
    fields = node.field_values.by_name()
    if not filters.keeps_column(fields):
        return None
    repo = str(content.get("repository", {}).get("nameWithOwner", ""))
    pull_request = PullRequestNode.model_validate(content) if kind == "PullRequest" else None
    base = pull_request or IssueNode.model_validate(content)
    labels = [label.name for label in base.labels.nodes]
    assignees = [actor.login for actor in base.assignees.nodes]
    author = base.author.login if base.author else ""
    item_type = "pull_request" if pull_request else "issue"
    if not filters.keeps_content(
        kind=item_type,
        repo=repo,
        state=base.state,
        labels=labels,
        assignees=assignees,
        author=author,
    ):
        return None
    return ProjectItem(
        id=f"{repo}#{base.number}",
        title=base.title,
        url=base.url,
        repo=repo,
        project_title=project_title,
        project_url=project_url,
        project_column=fields.get(filters.status_field, ""),
        project_fields=json.dumps(fields, ensure_ascii=False, sort_keys=True),
        item_type=item_type,
        item_number=base.number,
        item_title=base.title,
        item_body=base.body or "",
        item_url=base.url,
        item_state=base.state,
        item_author=author,
        item_labels=labels,
        item_assignees=assignees,
        item_milestone=base.milestone.title if base.milestone else "",
        item_created_at=base.created_at,
        pull_request_head_ref=pull_request.head_ref_name if pull_request else "",
        pull_request_base_ref=pull_request.base_ref_name if pull_request else "",
        pull_request_head_sha=pull_request.head_ref_oid if pull_request else "",
        pull_request_is_draft=pull_request.is_draft if pull_request else False,
    )


def _project_feed(filters: ProjectFilters) -> Discovery[ProjectItemNode, ProjectItem]:
    key = f"project:{filters.model_dump_json()}"
    feed = _FEEDS.get(key)
    if feed is None:
        view_filter = filters.view_filter()
        # The project title and URL arrive with every page; keep the latest for `to_item`.
        meta: dict[str, str] = {"title": "", "url": ""}

        def fetch(after: str | None) -> Any:
            project, items = _CLIENT.project_items(
                filters.owner, filters.project, view_filter=view_filter, after=after
            )
            meta["title"], meta["url"] = project.title, project.url
            return items

        feed = Discovery(
            fetch_page=fetch,
            parse_page=lambda connection: parse_nodes(connection, ProjectItemNode),
            keep=lambda node: _project_item(filters, meta["title"], meta["url"], node) is not None,
            to_item=lambda node: _project_item(  # type: ignore[arg-type, return-value]
                filters, meta["title"], meta["url"], node
            ),
        )
        _FEEDS[key] = feed
    return feed


def github_issues(
    repo: str,
    labels: str | list[str] | None = None,
    exclude_labels: str | list[str] | None = None,
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
    labels: str | list[str] | None = None,
    exclude_labels: str | list[str] | None = None,
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
    merge_state: str | list[str] | None = None,
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


def github_project_items(
    owner: str,
    project: int,
    column: str | list[str],
    status_field: str = "Status",
    content: str = "all",
    repo: str | None = None,
    state: str = "open",
    labels: str | list[str] | None = None,
    exclude_labels: str | list[str] | None = None,
    assignee: str | None = None,
    author: str | None = None,
) -> ProjectItem | None:
    """Return the next issue or pull request sitting in a GitHub Project column."""
    filters = ProjectFilters(
        owner=owner,
        project=project,
        column=column,
        status_field=status_field,
        content=content,  # type: ignore[arg-type]
        repo=repo,
        state=state,  # type: ignore[arg-type]
        labels=labels,
        exclude_labels=exclude_labels,
        assignee=assignee,
        author=author,
    )
    return _project_feed(filters).next_item()


def register(app: Curupira) -> None:
    """Register GitHub triggers on ``app``."""
    app.trigger(github_issues)
    app.trigger(github_pull_requests)
    app.trigger(github_project_items)
    app.param_check("github-project-items", _check_project_filters)
    app.param_check("github-issues", _check_issue_filters)
    app.param_check("github-pull-requests", _check_pull_request_filters)
