"""Task identities, resolved execution snapshots, and persistence contracts."""

import json
from pathlib import Path

from pydantic import AwareDatetime, BaseModel, SerializeAsAny, model_validator

from curupira.models.base import Identifier, NonEmptyString, ValidatedModel
from curupira.models.configuration import AutomationConfiguration
from curupira.models.profiles import CliProfile


class TaskIdentity(ValidatedModel):
    """One automation's work on a source item or scheduled occurrence."""

    automation_id: Identifier
    repo: NonEmptyString
    task_type: NonEmptyString
    id: NonEmptyString

    @property
    def key(self) -> str:
        """Return a collision-free canonical key shared by all consumers."""
        return json.dumps(
            [self.automation_id, self.repo, self.task_type, self.id], separators=(",", ":")
        )


class ResolvedAutomation(ValidatedModel):
    """A validated automation with effective profile, workspace, and timezone."""

    automation_id: Identifier
    configuration: AutomationConfiguration
    profile: CliProfile
    workspace_path: Path
    repository_id: Identifier
    remote: NonEmptyString
    setup_script: str | None = None
    identity_repo: NonEmptyString
    timezone: NonEmptyString | None = None


class Task(ValidatedModel):
    """Resolved task passed unchanged from discovery to execution and persistence.

    Attributes:
        identity: Canonical identity of the source item or occurrence.
        automation: Resolved automation snapshot that discovered the task.
        title: Human-readable title for logs, the TUI, and ``${task_title}``.
        url: Link shown in status output and available as ``${task_url}``.
        item: Trigger-specific Pydantic payload used to interpolate the prompt.
        scheduled_for: Cron occurrence, only for cron tasks.
    """

    identity: TaskIdentity
    automation: ResolvedAutomation
    title: str
    url: str
    item: SerializeAsAny[ValidatedModel]
    scheduled_for: AwareDatetime | None = None

    @model_validator(mode="before")
    @classmethod
    def parse_typed_item(cls, data: object) -> object:
        """Validate ``item`` with the trigger's ``item_model`` when loading raw payloads."""
        if not isinstance(data, dict):
            return data
        item = data.get("item")
        if item is None or isinstance(item, BaseModel):
            return data
        identity = data.get("identity")
        if isinstance(identity, dict):
            task_type = identity.get("task_type")
        else:
            task_type = getattr(identity, "task_type", None)
        if not isinstance(task_type, str):
            return data
        from curupira.tasks.registry import get

        return {**data, "item": get(task_type).item_model.model_validate(item)}

    @model_validator(mode="after")
    def validate_source(self) -> "Task":
        """Keep task identity consistent with its resolved automation and trigger."""
        config = self.automation.configuration
        if (
            self.identity.automation_id != self.automation.automation_id
            or self.identity.repo != self.automation.identity_repo
            or self.identity.task_type != config.trigger_type
        ):
            raise ValueError("task identity must match its resolved automation")
        from curupira.tasks.registry import get

        trigger = get(config.trigger_type)
        trigger.validate_task(self)
        if type(self.item) is not trigger.item_model:
            item = trigger.item_model.model_validate(self.item.model_dump())
            return self.model_copy(update={"item": item})
        return self


class RunningCodingSession(ValidatedModel):
    """The original task snapshot and native session required for resumption."""

    task: Task
    session_id: NonEmptyString
    message: NonEmptyString


class CronRunState(ValidatedModel):
    """A cron automation's creation time and claimed occurrence watermark."""

    automation_id: Identifier
    created_at: AwareDatetime
    last_execution_at: AwareDatetime | None = None
    last_scheduled_for: AwareDatetime | None = None
    pending_scheduled_for: AwareDatetime | None = None
