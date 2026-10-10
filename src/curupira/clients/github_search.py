"""Compile typed GitHub automation filters into GitHub Search query strings."""

from __future__ import annotations

from curupira.models.configuration import (
    GitHubAutomationConfiguration,
    IssueAutomationConfiguration,
    PullRequestAutomationConfiguration,
)


def quote_search_value(value: str) -> str:
    """Quote a search qualifier value when it contains whitespace or special characters."""
    if any(character.isspace() for character in value) or any(
        character in value for character in ('"', ":", ",")
    ):
        escaped = value.replace('"', r"\"")
        return f'"{escaped}"'
    return value


def _append_common_filters(parts: list[str], configuration: GitHubAutomationConfiguration) -> None:
    if configuration.state == "open":
        parts.append("is:open")
    elif configuration.state == "closed":
        parts.append("is:closed")
    for label in configuration.labels:
        parts.append(f"label:{quote_search_value(label)}")
    for label in configuration.exclude_labels:
        parts.append(f"-label:{quote_search_value(label)}")
    if configuration.assignee is not None:
        if configuration.assignee == "none":
            parts.append("no:assignee")
        elif configuration.assignee == "any":
            parts.append("assignee:*")
        else:
            parts.append(f"assignee:{quote_search_value(configuration.assignee)}")
    if configuration.author is not None:
        parts.append(f"author:{quote_search_value(configuration.author)}")
    if configuration.milestone is not None:
        parts.append(f"milestone:{quote_search_value(configuration.milestone)}")
    if configuration.project is not None:
        parts.append(f"project:{quote_search_value(configuration.project)}")


def _append_issue_filters(parts: list[str], configuration: IssueAutomationConfiguration) -> None:
    if configuration.linked_pull_request is True:
        parts.append("linked:pr")
    elif configuration.linked_pull_request is False:
        parts.append("-linked:pr")


def _append_pull_request_filters(
    parts: list[str], configuration: PullRequestAutomationConfiguration
) -> None:
    if configuration.draft is True:
        parts.append("draft:true")
    elif configuration.draft is False:
        parts.append("draft:false")
    if configuration.base is not None:
        parts.append(f"base:{quote_search_value(configuration.base)}")
    if configuration.head is not None:
        parts.append(f"head:{quote_search_value(configuration.head)}")
    if configuration.review is not None:
        parts.append(f"review:{configuration.review}")
    if configuration.ci_status is not None:
        parts.append(f"status:{configuration.ci_status}")
    if configuration.linked_issue is True:
        parts.append("linked:issue")
    elif configuration.linked_issue is False:
        parts.append("-linked:issue")


def build_github_search_query(
    configuration: GitHubAutomationConfiguration,
    *,
    item_kind: str,
) -> str:
    """Build a GitHub Search query from typed automation filters."""
    parts = [f"repo:{configuration.repo}"]
    parts.append("is:issue" if item_kind == "issue" else "is:pr")
    _append_common_filters(parts, configuration)
    if isinstance(configuration, IssueAutomationConfiguration):
        _append_issue_filters(parts, configuration)
    if isinstance(configuration, PullRequestAutomationConfiguration):
        _append_pull_request_filters(parts, configuration)
    parts.append(f"sort:{configuration.sort}")
    return " ".join(parts)


def matches_pull_request_post_filters(
    *,
    mergeable: str | None,
    merge_state_status: str | None,
    configuration: PullRequestAutomationConfiguration,
) -> bool:
    """Apply GraphQL-only pull-request filters that Search cannot express."""
    if configuration.mergeable is True and mergeable != "MERGEABLE":
        return False
    if configuration.mergeable is False and mergeable != "CONFLICTING":
        return False
    return not (configuration.merge_state and merge_state_status not in configuration.merge_state)
