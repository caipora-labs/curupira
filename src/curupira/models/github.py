"""Validated GitHub CLI boundary payloads."""

from pydantic import Field

from curupira.models.base import (
    BoundaryModel,
    BoundedLimit,
    GitHubRepository,
    NonEmptyString,
    ValidatedModel,
)

DEFAULT_ISSUE_JSON_FIELDS = ("number", "title", "body", "url", "state", "labels")


class GhIssueSearchRequest(ValidatedModel):
    """A GitHub issue query.

    Attributes:
        repo: GitHub repository in ``owner/repository`` form.
        query: GitHub Search query passed to ``gh search``.
        limit: Maximum number of results requested.
    """

    repo: GitHubRepository
    query: NonEmptyString
    limit: BoundedLimit = 1


class GhPullRequestSearchRequest(GhIssueSearchRequest):
    """A GitHub pull request query.

    Attributes:
        jq: Optional ``gh --jq`` filter applied to the listed pull requests.
    """

    jq: NonEmptyString | None = None


class GhLabel(BoundaryModel):
    """A GitHub label.

    Attributes:
        name: Label name.
    """

    name: str


class GhIssue(BoundaryModel):
    """An issue received from GitHub.

    Attributes:
        number: Positive issue number.
        title: Issue title.
        body: Optional Markdown body.
        url: Web URL of the issue.
        state: Optional issue state reported by GitHub.
        labels: Labels attached to the issue.
    """

    number: int = Field(gt=0)
    title: str
    body: str | None = None
    url: str
    state: str | None = None
    labels: tuple[GhLabel, ...] = ()


class GhPullRequest(GhIssue):
    """A pull request with branch metadata.

    Attributes:
        is_draft: Whether the pull request is a draft, when reported.
        head_ref_name: Source branch name.
        base_ref_name: Target branch name.
    """

    is_draft: bool | None = Field(default=None, validation_alias="isDraft")
    head_ref_name: str | None = Field(default=None, validation_alias="headRefName")
    base_ref_name: str | None = Field(default=None, validation_alias="baseRefName")
