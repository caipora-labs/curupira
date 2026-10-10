"""Trigger-specific task payloads exposed to prompt templates."""

from curupira.models.base import NonEmptyString, ValidatedModel


class IssueItem(ValidatedModel):
    """GitHub issue fields available as prompt placeholders.

    Attributes:
        issue_number: Issue number as a string.
        issue_title: Issue title.
        issue_body: Issue body, or empty when absent.
        issue_url: HTML URL of the issue.
    """

    issue_number: NonEmptyString
    issue_title: str
    issue_body: str = ""
    issue_url: NonEmptyString


class PullRequestItem(ValidatedModel):
    """Pull-request fields shared by GitHub and Azure DevOps triggers.

    Attributes:
        pull_request_number: Pull-request number or ID as a string.
        pull_request_title: Pull-request title.
        pull_request_body: Description body, or empty when absent.
        pull_request_url: HTML URL of the pull request.
        pull_request_is_draft: Whether the pull request is a draft.
        pull_request_head_ref: Source branch name.
        pull_request_base_ref: Target branch name.
    """

    pull_request_number: NonEmptyString
    pull_request_title: str
    pull_request_body: str = ""
    pull_request_url: NonEmptyString
    pull_request_is_draft: bool | None = None
    pull_request_head_ref: str | None = None
    pull_request_base_ref: str | None = None


class CronItem(ValidatedModel):
    """Cron occurrences expose only the common prompt placeholders."""


class TrelloCardItem(ValidatedModel):
    """Trello card fields available as prompt placeholders.

    Attributes:
        card_id: Trello card ID preserved as a string.
        card_title: Card name.
        card_body: Card description, or empty when absent.
        card_url: HTML URL of the card.
        card_list_id: ID of the list that currently holds the card.
    """

    card_id: NonEmptyString
    card_title: str
    card_body: str = ""
    card_url: NonEmptyString
    card_list_id: str = ""
