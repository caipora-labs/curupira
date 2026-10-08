"""Shared annotated types and model bases enforce one rule each."""

from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from curupira.agents.base import CliEvent
from curupira.models import (
    AzPullRequest,
    CodexCliProfile,
    CommandRequest,
    GhIssue,
    GhIssueSearchRequest,
    OpenCodeCliProfile,
    PullRequestAutomationConfiguration,
)
from curupira.models.base import (
    AzureRepository,
    BoundedLimit,
    GitHubRepository,
    OutputLimit,
    RelativeScriptPath,
    TimezoneName,
)


@pytest.mark.parametrize("value", ["acme/api", "my.org/my_repo-2"])
def test_github_repository_accepts_owner_repository(value: str) -> None:
    assert TypeAdapter(GitHubRepository).validate_python(value) == value


@pytest.mark.parametrize("value", ["acme", "acme/api/extra", "../api", "acme/..", "a b/c", ""])
def test_github_repository_rejects_other_shapes(value: str) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(GitHubRepository).validate_python(value)


def test_azure_repository_requires_three_segments() -> None:
    adapter = TypeAdapter(AzureRepository)
    assert adapter.validate_python("contoso/project/api") == "contoso/project/api"
    for value in ("contoso/api", "contoso/../api", "contoso/project/api/extra"):
        with pytest.raises(ValidationError, match="repo"):
            adapter.validate_python(value)


def test_timezone_name_requires_a_known_iana_zone() -> None:
    adapter = TypeAdapter(TimezoneName)
    assert adapter.validate_python("America/Sao_Paulo") == "America/Sao_Paulo"
    with pytest.raises(ValidationError, match="unknown timezone"):
        adapter.validate_python("Mars/Olympus")


@pytest.mark.parametrize("value", ["", " ", "/etc/x", "../x", "a/../x", r"C:\x", r"\x"])
def test_relative_script_path_rejects_absolute_and_traversal(value: str) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(RelativeScriptPath).validate_python(value)


@pytest.mark.parametrize(
    ("annotation", "value"),
    [(BoundedLimit, "5"), (BoundedLimit, 0), (BoundedLimit, True), (OutputLimit, 1023)],
)
def test_numeric_limits_are_strict_and_bounded(annotation: Any, value: object) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(annotation).validate_python(value)


@pytest.mark.parametrize(
    ("model", "data"),
    [
        (OpenCodeCliProfile, {"auto_approve": "true"}),
        (CodexCliProfile, {"auto_review": 1}),
        (CommandRequest, {"executable": "gh", "capture_output": "yes"}),
        (GhIssueSearchRequest, {"repo": "acme/api", "query": "q", "limit": "3"}),
    ],
)
def test_configuration_flags_and_counts_reject_coercion(
    model: type[OpenCodeCliProfile | CodexCliProfile | CommandRequest | GhIssueSearchRequest],
    data: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate(data)


def test_boundary_models_ignore_unknown_fields_and_are_immutable() -> None:
    issue = GhIssue.model_validate(
        {"number": 1, "title": "t", "url": "u", "labels": [{"name": "x", "color": "f00"}], "new": 1}
    )
    event = CliEvent.model_validate_json('{"type": "text", "sessionID": "s", "extra": true}')
    pull_request = AzPullRequest.model_validate({"pullRequestId": 3, "title": "t"})

    assert issue.labels[0].name == "x"
    assert event.session_id == "s"
    for model, field in ((issue, "title"), (event, "type"), (pull_request, "title")):
        with pytest.raises(ValidationError, match="frozen"):
            setattr(model, field, "changed")


def test_pull_request_prompt_accepts_only_pull_request_placeholders() -> None:
    data = {"repo": "acme/api", "query": "is:open"}
    PullRequestAutomationConfiguration.model_validate(
        data | {"prompt": "Review ${pull_request_number} on ${pull_request_head_ref}"}
    )
    with pytest.raises(ValidationError, match="issue_number"):
        PullRequestAutomationConfiguration.model_validate(data | {"prompt": "${issue_number}"})
