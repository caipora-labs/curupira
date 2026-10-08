"""Validated Azure DevOps CLI boundary payloads."""

from typing import Literal

from pydantic import Field

from curupira.models.base import BoundaryModel, BoundedLimit, NonEmptyString, ValidatedModel

AzurePullRequestStatus = Literal["active", "completed", "abandoned", "all"]


class AzPullRequestSearchRequest(ValidatedModel):
    """An Azure DevOps pull request list query.

    Attributes:
        organization: Azure DevOps organization name.
        project: Project name within the organization.
        repository: Repository name within the project.
        limit: Maximum number of results requested.
        status: Pull-request status filter.
        source_branch: Optional source branch filter.
        target_branch: Optional target branch filter.
    """

    organization: NonEmptyString
    project: NonEmptyString
    repository: NonEmptyString
    limit: BoundedLimit = 1
    status: AzurePullRequestStatus = "active"
    source_branch: NonEmptyString | None = None
    target_branch: NonEmptyString | None = None


class AzHref(BoundaryModel):
    """A single Azure DevOps hypermedia reference.

    Attributes:
        href: Optional link target.
    """

    href: str | None = None


class AzPullRequestLinks(BoundaryModel):
    """Optional Azure DevOps hypermedia links.

    Attributes:
        web: Human-facing web link, when present.
    """

    web: AzHref | None = None


class AzPullRequest(BoundaryModel):
    """A pull request received from Azure DevOps.

    Attributes:
        pull_request_id: Positive pull-request identifier.
        title: Pull-request title.
        description: Optional Markdown description.
        url: Optional REST API URL.
        status: Optional pull-request status.
        is_draft: Whether the pull request is a draft, when reported.
        source_ref_name: Fully qualified source ref (``refs/heads/...``).
        target_ref_name: Fully qualified target ref (``refs/heads/...``).
        links: Optional hypermedia links.
    """

    pull_request_id: int = Field(gt=0, validation_alias="pullRequestId")
    title: str
    description: str | None = None
    url: str | None = None
    status: str | None = None
    is_draft: bool | None = Field(default=None, validation_alias="isDraft")
    source_ref_name: str | None = Field(default=None, validation_alias="sourceRefName")
    target_ref_name: str | None = Field(default=None, validation_alias="targetRefName")
    links: AzPullRequestLinks | None = Field(default=None, validation_alias="_links")

    def web_url(self) -> str | None:
        """Prefer the human-facing web link when Azure includes it."""
        if self.links is not None and self.links.web is not None and self.links.web.href:
            return self.links.web.href
        return self.url
