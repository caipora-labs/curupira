"""Validated GitHub GraphQL boundary payloads."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from curupira.models.base import NonEmptyString, ValidatedModel

GitHubMergeableState = Literal["MERGEABLE", "CONFLICTING", "UNKNOWN"]
GitHubMergeStateStatus = Literal[
    "BEHIND",
    "BLOCKED",
    "CLEAN",
    "DIRTY",
    "DRAFT",
    "HAS_HOOKS",
    "UNKNOWN",
    "UNSTABLE",
]


class GitHubSearchRequest(ValidatedModel):
    """A compiled GitHub Search request for GraphQL discovery."""

    repo: NonEmptyString
    query: NonEmptyString
    limit: int = Field(default=1, ge=1, le=1000)
    item_kind: Literal["issue", "pull_request"] = "issue"


class GhLabel(BaseModel):
    """A GitHub label; tolerate additional upstream response fields."""

    model_config = ConfigDict(extra="ignore", frozen=True)
    name: str


class GhIssue(BaseModel):
    """An issue received from GitHub GraphQL."""

    model_config = ConfigDict(extra="ignore", frozen=True)
    number: int = Field(gt=0)
    title: str
    body: str | None = None
    url: str
    state: str | None = None
    labels: list[GhLabel] = Field(default_factory=list)


class GhPullRequest(GhIssue):
    """A pull request with branch and merge metadata."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)
    is_draft: bool | None = Field(default=None, validation_alias="isDraft")
    head_ref_name: str | None = Field(default=None, validation_alias="headRefName")
    base_ref_name: str | None = Field(default=None, validation_alias="baseRefName")
    mergeable: GitHubMergeableState | None = None
    merge_state_status: GitHubMergeStateStatus | None = Field(
        default=None, validation_alias="mergeStateStatus"
    )


# Compatibility aliases for older imports during the GraphQL migration.
GhIssueSearchRequest = GitHubSearchRequest
GhPullRequestSearchRequest = GitHubSearchRequest
DEFAULT_ISSUE_JSON_FIELDS = ("number", "title", "body", "url", "state", "labels")
