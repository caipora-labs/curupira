"""Task identities, resolved execution snapshots, and persistence contracts."""

import hashlib
import json
from pathlib import Path

from pydantic import AwareDatetime, BaseModel, SerializeAsAny, model_validator

from curupira.models.base import Identifier, NonEmptyString, ValidatedModel
from curupira.models.configuration import AutomationConfiguration
from curupira.models.items import IssueItem, PullRequestItem
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

    @property
    def dispatch_key(self) -> str:
        """Return the in-memory admission key, including PR head revision."""
        if self.identity.task_type == "github-pull-requests" and isinstance(
            self.item, PullRequestItem
        ):
            return json.dumps(
                [
                    self.identity.key,
                    self.item.pull_request_head_sha,
                    self.state_fingerprint,
                ],
                separators=(",", ":"),
            )
        return self.identity.key

    @property
    def state_key(self) -> str:
        """Return the durable completion key for one automation-scoped source item."""
        return self.identity.key

    @property
    def state_fingerprint(self) -> str:
        """Return a stable fingerprint of source state relevant to repeating work.

        Pull-request fingerprints use head SHA, draft flag, title, and body.
        Mergeability, merge-state status, and check conclusions are omitted so check
        or conflict transitions alone do not re-admit an unchanged completed snapshot.
        """
        if isinstance(self.item, PullRequestItem):
            payload = {
                "title": self.title,
                "url": self.url,
                "body": self.item.pull_request_body,
                "is_draft": self.item.pull_request_is_draft,
                "head_sha": self.item.pull_request_head_sha,
            }
        elif isinstance(self.item, IssueItem):
            payload = {
                "title": self.title,
                "url": self.url,
                "body": self.item.issue_body,
            }
        else:
            payload = {
                "title": self.title,
                "url": self.url,
                "item": self.item.model_dump(mode="json"),
            }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

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


class CompletedTaskState(ValidatedModel):
    """A completed source snapshot and the next external action, if any."""

    fingerprint: NonEmptyString
    next_action: NonEmptyString


class CronRunState(ValidatedModel):
    """A cron automation's creation time and claimed occurrence watermark."""

    automation_id: Identifier
    created_at: AwareDatetime
    last_execution_at: AwareDatetime | None = None
    last_scheduled_for: AwareDatetime | None = None
    pending_scheduled_for: AwareDatetime | None = None
