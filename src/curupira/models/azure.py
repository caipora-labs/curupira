"""Validated Azure DevOps CLI boundary payloads."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from curupira.models.base import NonEmptyString, ValidatedModel

AzurePullRequestStatus = Literal["active", "completed", "abandoned", "all"]


class AzPullRequestSearchRequest(ValidatedModel):
    """An Azure DevOps pull request list query."""

    organization: NonEmptyString
    project: NonEmptyString
    repository: NonEmptyString
    limit: int = Field(default=1, ge=1, le=1000)
    status: AzurePullRequestStatus = "active"
    source_branch: NonEmptyString | None = None
    target_branch: NonEmptyString | None = None


class AzHref(BaseModel):
    """A single Azure DevOps hypermedia reference."""

    model_config = ConfigDict(extra="ignore", frozen=True)
    href: str | None = None


class AzPullRequestLinks(BaseModel):
    """Optional Azure DevOps hypermedia links."""

    model_config = ConfigDict(extra="ignore", frozen=True)
    web: AzHref | None = None


class AzPullRequest(BaseModel):
    """A pull request received from Azure DevOps."""

    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)
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
