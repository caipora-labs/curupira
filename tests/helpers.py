"""Reusable typed task snapshots and controlled CLI adapters for tests."""

from pathlib import Path

from curupi.config import ApplicationSettings
from curupi.models import ResolvedAutomation, Task, TaskIdentity


def resolved_automation(
    path: Path, name: str = "issues", trigger: str = "issue"
) -> ResolvedAutomation:
    """Resolve one automation through the real configuration boundary."""
    config: dict[str, object] = {
        "trigger_type": trigger,
        "repo": "acme/api",
        "path": path,
        "prompt": "Handle ${task_type} ${task_number}: ${task_title}",
    }
    if trigger == "cron":
        config.update(schedule="0 9 * * *", start_date="2026-10-01T00:00:00+00:00")
    else:
        config["query"] = "is:open"
    settings = ApplicationSettings.model_validate(
        {"coding_agents": {"automations": {name: config}}}
    )
    return settings.resolve_automations()[name]


def issue_task(path: Path, number: int = 42, name: str = "issues") -> Task:
    """Create an issue task with a fully resolved, validated execution snapshot."""
    automation = resolved_automation(path, name)
    return Task(
        identity=TaskIdentity(
            automation_id=name, repo="acme/api", task_type="issue", id=str(number)
        ),
        automation=automation,
        title=f"Task {number}",
        body="Details",
        url=f"https://github.com/acme/api/issues/{number}",
    )


def pull_request_task(path: Path, number: int = 12, name: str = "reviews") -> Task:
    """Create a pull request snapshot with its native branch metadata."""
    return Task(
        identity=TaskIdentity(
            automation_id=name, repo="acme/api", task_type="pull_request", id=str(number)
        ),
        automation=resolved_automation(path, name, "pull_request"),
        title="Review",
        url=f"https://github.com/acme/api/pull/{number}",
        is_draft=True,
        head_ref_name="feature",
        base_ref_name="main",
    )
