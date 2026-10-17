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


class IssueNode(_GraphQLModel):
    id: str
    number: int
    title: str
    body: str | None = None
    url: str
    state: str
    author: Actor | None = None
    labels: LabelConnection = Field(default_factory=LabelConnection)


class PullRequestNode(IssueNode):
    head_ref_name: str
    base_ref_name: str
    head_ref_oid: str
    is_draft: bool
    mergeable: str
    merge_state_status: str


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
