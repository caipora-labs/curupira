"""Reusable typed task snapshots and controlled CLI adapters for tests."""

from pathlib import Path
from typing import Any

from curupira.config import ApplicationSettings
from curupira.models import ResolvedAutomation, Task, TaskIdentity
from curupira.models.items import IssueItem, PullRequestItem


def settings_dict(
    automations: dict[str, dict[str, Any]],
    *,
    repositories: dict[str, dict[str, Any]] | None = None,
    agents: dict[str, Any] | None = None,
    settings: dict[str, Any] | None = None,
    assistant: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a complete ApplicationSettings payload for the split TOML shape."""
    normalized: dict[str, dict[str, Any]] = {}
    for name, automation in automations.items():
        item = dict(automation)
        item.setdefault("repository", "api")
        item.pop("query", None)
        item.pop("jq", None)
        item.pop("path", None)
        item.pop("setup_script", None)
        trigger = item.get("trigger_type", "github-issues")
        if trigger in {"github-issues", "github-pull-requests", "azure-cli-pull-requests"}:
            item.setdefault(
                "repo",
                "contoso/api-project/api" if trigger == "azure-cli-pull-requests" else "acme/api",
            )
        if trigger == "github-issues":
            item.setdefault("labels", ["agent-ready"])
        normalized[name] = item
    payload: dict[str, Any] = {
        "repositories": repositories
        or {
            "api": {"remote": "https://github.com/acme/api.git"},
            "azure-api": {"remote": "https://dev.azure.com/contoso/api-project/_git/api"},
        },
        "agents": agents
        or {
            "defaults": {"profile": "opencode"},
            "profiles": {"opencode": {"provider": "opencode"}},
        },
        "automations": normalized,
    }
    if settings is not None:
        payload["settings"] = settings
    if assistant is not None:
        payload["assistant"] = assistant
    # Point azure automations at the azure-api repository alias by default.
    for item in normalized.values():
        if (
            item.get("trigger_type") == "azure-cli-pull-requests"
            and item.get("repository") == "api"
        ):
            item["repository"] = "azure-api"
    return payload


def resolved_automation(
    path: Path,
    name: str = "issues",
    trigger: str = "github-issues",
    *,
    repository: str = "api",
    **overrides: object,
) -> ResolvedAutomation:
    """Resolve one automation through the real configuration boundary."""
    forge_repo = "contoso/api-project/api" if trigger == "azure-cli-pull-requests" else "acme/api"
    remote = (
        "https://dev.azure.com/contoso/api-project/_git/api"
        if trigger == "azure-cli-pull-requests"
        else "https://github.com/acme/api.git"
    )
    config: dict[str, object] = {
        "trigger_type": trigger,
        "repository": repository,
        "prompt": "Handle ${task_type} ${task_number}: ${task_title}",
    }
    if trigger == "cron":
        config.update(schedule="0 9 * * *", start_date="2026-10-01T00:00:00+00:00")
    elif trigger == "trello-cli-cards":
        config["board_id"] = "board123"
    elif trigger == "azure-cli-pull-requests":
        config["repo"] = forge_repo
    else:
        config["repo"] = forge_repo
        config["labels"] = ["agent-ready"]
    config.update(overrides)
    settings = ApplicationSettings.model_validate(
        {
            "repositories": {repository: {"remote": remote, "path": path}},
            "agents": {"profiles": {"opencode": {"provider": "opencode"}}},
            "automations": {name: config},
        }
    )
    return settings.resolve_automations()[name]


def issue_task(path: Path, number: int = 42, name: str = "issues") -> Task:
    """Create an issue task with a fully resolved, validated execution snapshot."""
    automation = resolved_automation(path, name)
    return Task(
        identity=TaskIdentity(
            automation_id=name, repo="acme/api", task_type="github-issues", id=str(number)
        ),
        automation=automation,
        title=f"Task {number}",
        url=f"https://github.com/acme/api/issues/{number}",
        item=IssueItem(
            issue_number=str(number),
            issue_title=f"Task {number}",
            issue_body="Details",
            issue_url=f"https://github.com/acme/api/issues/{number}",
        ),
    )


def pull_request_task(path: Path, number: int = 12, name: str = "reviews") -> Task:
    """Create a pull request snapshot with its native branch metadata."""
    return Task(
        identity=TaskIdentity(
            automation_id=name,
            repo="acme/api",
            task_type="github-pull-requests",
            id=str(number),
        ),
        automation=resolved_automation(path, name, "github-pull-requests"),
        title="Review",
        url=f"https://github.com/acme/api/pull/{number}",
        item=PullRequestItem(
            pull_request_number=str(number),
            pull_request_title="Review",
            pull_request_url=f"https://github.com/acme/api/pull/{number}",
            pull_request_is_draft=True,
            pull_request_head_ref="feature",
            pull_request_base_ref="main",
        ),
    )
