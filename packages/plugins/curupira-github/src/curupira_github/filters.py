"""Typed automation filters and their compilation into GitHub Search query strings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

REPO_PATTERN = r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$"

SearchState = Literal["open", "closed", "all"]
SortOrder = Literal[
    "created-asc",
    "created-desc",
    "updated-asc",
    "updated-desc",
    "comments-asc",
    "comments-desc",
]
MergeState = Literal[
    "BEHIND", "BLOCKED", "CLEAN", "DIRTY", "DRAFT", "HAS_HOOKS", "UNKNOWN", "UNSTABLE"
]


class SearchFilters(BaseModel):
    """Filters shared by issue and pull-request automations."""

    model_config = ConfigDict(extra="forbid")

    repo: str = Field(pattern=REPO_PATTERN)
    state: SearchState = "open"
    labels: list[str] | None = None
    exclude_labels: list[str] | None = None
    assignee: str | None = None
    author: str | None = None
    milestone: str | None = None
    project: str | None = None
    sort: SortOrder | None = None

    @field_validator("repo")
    @classmethod
    def _reject_traversal(cls, value: str) -> str:
        if any(part in {".", ".."} for part in value.split("/")):
            raise ValueError("repo must not contain traversal segments")
        return value

    def shared_qualifiers(self) -> list[str]:
        """Return the Search qualifiers that both issues and pull requests accept."""
        qualifiers = [f"repo:{self.repo}", _STATE_QUALIFIERS[self.state]]
        qualifiers += [_qualifier("label", label) for label in self.labels or []]
        qualifiers += [f"-{_qualifier('label', label)}" for label in self.exclude_labels or []]
        qualifiers += _assignee_qualifiers(self.assignee)
        if self.author:
            qualifiers.append(_qualifier("author", self.author))
        if self.milestone:
            qualifiers.append(_qualifier("milestone", self.milestone))
        if self.project:
            qualifiers.append(_qualifier("project", self.project))
        return qualifiers


class IssueFilters(SearchFilters):
    """Filters for `github_issues` automations."""

    linked_pull_request: bool | None = None

    def search_query(self) -> str:
        qualifiers = ["is:issue", *self.shared_qualifiers()]
        if self.linked_pull_request is not None:
            qualifiers.append("linked:pr" if self.linked_pull_request else "-linked:pr")
        return _join(qualifiers, self.sort)


class PullRequestFilters(SearchFilters):
    """Filters for `github_pull_requests` automations."""

    draft: bool | None = None
    base: str | None = None
    head: str | None = None
    review: Literal["none", "required", "approved", "changes_requested"] | None = None
    ci_status: Literal["success", "failure", "pending"] | None = None
    linked_issue: bool | None = None
    mergeable: bool | None = None
    merge_state: list[MergeState] | None = None

    def search_query(self) -> str:
        qualifiers = ["is:pr", *self.shared_qualifiers()]
        if self.draft is not None:
            qualifiers.append(f"draft:{str(self.draft).lower()}")
        if self.base:
            qualifiers.append(_qualifier("base", self.base))
        if self.head:
            qualifiers.append(_qualifier("head", self.head))
        if self.review:
            qualifiers.append(f"review:{self.review}")
        if self.ci_status:
            qualifiers.append(f"status:{self.ci_status}")
        if self.linked_issue is not None:
            qualifiers.append("linked:issue" if self.linked_issue else "-linked:issue")
        return _join(qualifiers, self.sort)

    def keeps(self, *, mergeable_state: str, merge_state_status: str) -> bool:
        """Apply the GraphQL post-filters that Search cannot express."""
        if self.mergeable is not None:
            expected = "MERGEABLE" if self.mergeable else "CONFLICTING"
            if mergeable_state != expected:
                return False
        return not self.merge_state or merge_state_status in self.merge_state


_STATE_QUALIFIERS: dict[str, str] = {"open": "is:open", "closed": "is:closed", "all": ""}


def _join(qualifiers: list[str], sort: str | None) -> str:
    """Join qualifiers in a stable order, appending the sort qualifier last."""
    parts = [part for part in qualifiers if part]
    parts.append(f"sort:{sort or 'created-asc'}")
    return " ".join(parts)


def _assignee_qualifiers(assignee: str | None) -> list[str]:
    if assignee is None:
        return []
    if assignee == "none":
        return ["no:assignee"]
    if assignee == "any":
        return ["assignee:*"]
    return [_qualifier("assignee", assignee)]


def _qualifier(name: str, value: str) -> str:
    """Render `name:value`, quoting values that contain whitespace or `"`, `:`, `,`."""
    if any(char in value for char in ' \t\n":,'):
        escaped = value.replace('"', '\\"')
        return f'{name}:"{escaped}"'
    return f"{name}:{value}"
