"""Validated GitHub CLI boundary payloads."""

from pydantic import BaseModel, ConfigDict, Field

from curupira.models.base import NonEmptyString, ValidatedModel

DEFAULT_ISSUE_JSON_FIELDS = ("number", "title", "body", "url", "state", "labels")


class GhIssueSearchRequest(ValidatedModel):
    """A GitHub issue query."""

    repo: NonEmptyString
    query: NonEmptyString
    limit: int = Field(default=1, ge=1, le=1000)


class GhPullRequestSearchRequest(GhIssueSearchRequest):
    """A GitHub pull request query."""


class GhLabel(BaseModel):
    """A GitHub label; tolerate additional upstream response fields."""

    model_config = ConfigDict(extra="ignore", frozen=True)
    name: str


class GhIssue(BaseModel):
    """An issue received from GitHub."""

    model_config = ConfigDict(extra="ignore", frozen=True)
    number: int = Field(gt=0)
    title: str
    body: str | None = None
    url: str
    state: str | None = None
    labels: list[GhLabel] = Field(default_factory=list)


class GhPullRequest(GhIssue):
    """A pull request with branch metadata."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)
    is_draft: bool | None = Field(default=None, validation_alias="isDraft")
    head_ref_name: str | None = Field(default=None, validation_alias="headRefName")
    base_ref_name: str | None = Field(default=None, validation_alias="baseRefName")
