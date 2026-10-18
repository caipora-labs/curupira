"""Typed models for GitHub GraphQL responses and the task items returned to the host."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _GraphQLModel(BaseModel):
    """Parse GitHub's camelCase payloads and ignore fields the plugin does not use."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")


class Actor(_GraphQLModel):
    login: str


class LabelName(_GraphQLModel):
    name: str


class LabelConnection(_GraphQLModel):
    nodes: list[LabelName] = Field(default_factory=list)


class Milestone(_GraphQLModel):
    title: str


class ActorConnection(_GraphQLModel):
    nodes: list[Actor] = Field(default_factory=list)


class Comment(_GraphQLModel):
    author: Actor | None = None
    body: str = ""


class CommentConnection(_GraphQLModel):
    total_count: int = 0
    nodes: list[Comment] = Field(default_factory=list)


class LinkedReference(_GraphQLModel):
    number: int
    url: str


class ReferenceConnection(_GraphQLModel):
    nodes: list[LinkedReference] = Field(default_factory=list)


class Node(_GraphQLModel):
    id: str


class IssueNode(Node):
    number: int
    title: str
    body: str | None = None
    url: str
    state: str
    author: Actor | None = None
    labels: LabelConnection = Field(default_factory=LabelConnection)
    assignees: ActorConnection = Field(default_factory=ActorConnection)
    milestone: Milestone | None = None
    created_at: str = ""
    updated_at: str = ""
    comments: CommentConnection = Field(default_factory=CommentConnection)
    # Issue-only; absent from pull-request nodes.
    state_reason: str | None = None
    closed_by_pull_requests_references: ReferenceConnection = Field(
        default_factory=ReferenceConnection
    )


class StatusCheckRollup(_GraphQLModel):
    state: str


class CommitRef(_GraphQLModel):
    status_check_rollup: StatusCheckRollup | None = None


class CommitNode(_GraphQLModel):
    commit: CommitRef


class CommitConnection(_GraphQLModel):
    nodes: list[CommitNode] = Field(default_factory=list)


class RequestedReviewer(_GraphQLModel):
    login: str | None = None
    name: str | None = None


class ReviewRequest(_GraphQLModel):
    requested_reviewer: RequestedReviewer | None = None


class ReviewRequestConnection(_GraphQLModel):
    nodes: list[ReviewRequest] = Field(default_factory=list)


class PullRequestNode(IssueNode):
    head_ref_name: str
    base_ref_name: str
    head_ref_oid: str
    is_draft: bool
    mergeable: str
    merge_state_status: str
    review_decision: str | None = None
    changed_files: int = 0
    additions: int = 0
    deletions: int = 0
    commits: CommitConnection = Field(default_factory=CommitConnection)
    closing_issues_references: ReferenceConnection = Field(default_factory=ReferenceConnection)
    review_requests: ReviewRequestConnection = Field(default_factory=ReviewRequestConnection)

    @property
    def ci_status(self) -> str:
        """Combined check state of the head commit, or an empty string when none ran."""
        for node in self.commits.nodes:
            if node.commit.status_check_rollup is not None:
                return node.commit.status_check_rollup.state
        return ""

    @property
    def requested_reviewers(self) -> list[str]:
        names = (
            (request.requested_reviewer.login or request.requested_reviewer.name or "")
            for request in self.review_requests.nodes
            if request.requested_reviewer is not None
        )
        return [name for name in names if name]


class PageInfo(_GraphQLModel):
    has_next_page: bool
    end_cursor: str | None = None


class SearchConnection(_GraphQLModel):
    page_info: PageInfo
    nodes: list[Any] = Field(default_factory=list)


class SearchData(_GraphQLModel):
    search: SearchConnection


class GraphQLErrorEntry(_GraphQLModel):
    message: str


class SearchResponse(_GraphQLModel):
    data: SearchData | None = None
    errors: list[GraphQLErrorEntry] = Field(default_factory=list)


class IssueItem(BaseModel):
    """Issue task item; field names match the `${issue_*}` prompt placeholders."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    url: str
    repo: str
    issue_number: int
    issue_title: str
    issue_body: str
    issue_url: str
    issue_state: str
    issue_author: str
    issue_labels: list[str]
    issue_assignees: list[str]
    issue_milestone: str
    issue_created_at: str
    issue_updated_at: str
    issue_state_reason: str
    issue_linked_pull_requests: list[str]
    issue_comment_count: int
    issue_comments: str


class PullRequestItem(BaseModel):
    """Pull-request task item; field names match the `${pull_request_*}` prompt placeholders."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    url: str
    repo: str
    pull_request_number: int
    pull_request_title: str
    pull_request_body: str
    pull_request_url: str
    pull_request_is_draft: bool
    pull_request_head_ref: str
    pull_request_base_ref: str
    pull_request_head_sha: str
    pull_request_author: str
    pull_request_labels: list[str]
    pull_request_mergeable: str
    pull_request_merge_state_status: str
    pull_request_assignees: list[str]
    pull_request_milestone: str
    pull_request_created_at: str
    pull_request_updated_at: str
    pull_request_review_decision: str
    pull_request_ci_status: str
    pull_request_changed_files: int
    pull_request_additions: int
    pull_request_deletions: int
    pull_request_closing_issues: list[str]
    pull_request_requested_reviewers: list[str]
    pull_request_comment_count: int
    pull_request_comments: str


class ProjectItemNode(Node):
    """One Projects v2 item: its field values plus the issue or pull request it wraps."""

    is_archived: bool = False
    field_values: FieldValueConnection
    content: dict[str, Any] | None = None


class FieldRef(_GraphQLModel):
    name: str = ""


class FieldValue(_GraphQLModel):
    """Any field value; only single-select, text, number, date and iteration carry data."""

    field: FieldRef | None = None
    name: str | None = None
    text: str | None = None
    number: float | None = None
    date: str | None = None
    title: str | None = None

    def rendered(self) -> str | None:
        for candidate in (self.name, self.text, self.date, self.title):
            if candidate is not None:
                return candidate
        return None if self.number is None else f"{self.number:g}"


class FieldValueConnection(_GraphQLModel):
    nodes: list[FieldValue] = Field(default_factory=list)

    def by_name(self) -> dict[str, str]:
        """Map field name to rendered value, skipping untyped values (repository, PR links)."""
        values: dict[str, str] = {}
        for value in self.nodes:
            rendered = value.rendered()
            if value.field is not None and value.field.name and rendered is not None:
                values[value.field.name] = rendered
        return values


ProjectItemNode.model_rebuild()


ProjectItems = SearchConnection


class ProjectV2(_GraphQLModel):
    title: str
    url: str
    items: ProjectItems


class ProjectOwner(_GraphQLModel):
    project_v2: ProjectV2 | None = None


class ProjectData(_GraphQLModel):
    repository_owner: ProjectOwner | None = None


class ProjectResponse(_GraphQLModel):
    data: ProjectData | None = None
    errors: list[GraphQLErrorEntry] = Field(default_factory=list)


class ProjectItem(BaseModel):
    """Project item task; field names match the `${item_*}` / `${project_*}` placeholders."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    url: str
    repo: str
    project_title: str
    project_url: str
    project_column: str
    project_fields: str
    item_type: str
    item_number: int
    item_title: str
    item_body: str
    item_url: str
    item_state: str
    item_author: str
    item_labels: list[str]
    item_assignees: list[str]
    item_milestone: str
    item_created_at: str
    item_updated_at: str
    item_comment_count: int
    item_comments: str
    pull_request_head_ref: str
    pull_request_base_ref: str
    pull_request_head_sha: str
    pull_request_is_draft: bool
    pull_request_review_decision: str
    pull_request_ci_status: str
