"""Task identities, resolved execution snapshots, and persistence contracts."""

import json
from pathlib import Path

from pydantic import AwareDatetime, model_validator

from curupira.models.base import Identifier, NonEmptyString, ValidatedModel
from curupira.models.configuration import AutomationConfiguration, CronAutomationConfiguration
from curupira.models.profiles import CliProfile


class TaskIdentity(ValidatedModel):
    """One automation's work on a source item or scheduled occurrence.

    Attributes:
        automation_id: Name of the automation that discovered the task.
        repo: Repository identifier copied from the automation.
        task_type: Trigger type that produced the task.
        id: Source item number or scheduled occurrence timestamp.
    """

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
    """A validated automation with effective profile, workspace, and timezone.

    Attributes:
        automation_id: Name of the automation in the configuration.
        configuration: Automation definition with inherited values applied.
        profile: Effective CLI profile.
        workspace_path: Absolute base checkout path.
        timezone: Effective IANA timezone for cron automations.
    """

    automation_id: Identifier
    configuration: AutomationConfiguration
    profile: CliProfile
    workspace_path: Path
    timezone: NonEmptyString | None = None


class Task(ValidatedModel):
    """Resolved task passed unchanged from discovery to execution and persistence.

    Attributes:
        identity: Stable identity used for deduplication and persistence.
        automation: Resolved automation that discovered the task.
        title: Source item title, or the automation name for cron.
        body: Optional source item body.
        url: Web URL of the source item.
        is_draft: Whether a pull request is a draft, when known.
        head_ref_name: Pull-request source branch, when known.
        base_ref_name: Pull-request target branch, when known.
        scheduled_for: Occurrence time; required for cron tasks only.
    """

    identity: TaskIdentity
    automation: ResolvedAutomation
    title: str
    body: str | None = None
    url: str
    is_draft: bool | None = None
    head_ref_name: str | None = None
    base_ref_name: str | None = None
    scheduled_for: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "Task":
        """Keep task identity consistent with its resolved automation."""
        config = self.automation.configuration
        if (
            self.identity.automation_id != self.automation.automation_id
            or self.identity.repo != config.repo
            or self.identity.task_type != config.trigger_type
        ):
            raise ValueError("task identity must match its resolved automation")
        if isinstance(config, CronAutomationConfiguration):
            if self.scheduled_for is None:
                raise ValueError("cron tasks require scheduled_for")
            if self.identity.id != str(int(self.scheduled_for.timestamp())):
                raise ValueError("cron identity must match its scheduled occurrence")
        elif self.scheduled_for is not None:
            raise ValueError("non-cron tasks must not contain a scheduled occurrence")
        return self


class RunningCodingSession(ValidatedModel):
    """The original task snapshot and native session required for resumption.

    Attributes:
        task: Task snapshot taken when the session started.
        session_id: Provider-native session identifier.
        message: Rendered prompt originally sent to the agent.
    """

    task: Task
    session_id: NonEmptyString
    message: NonEmptyString


class CronRunState(ValidatedModel):
    """A cron automation's creation time and claimed occurrence watermark.

    Attributes:
        automation_id: Name of the cron automation.
        created_at: When the automation was first recorded.
        last_execution_at: When an occurrence last started.
        last_scheduled_for: Latest occurrence already claimed.
        pending_scheduled_for: Occurrence claimed but not yet finished.
    """

    automation_id: Identifier
    created_at: AwareDatetime
    last_execution_at: AwareDatetime | None = None
    last_scheduled_for: AwareDatetime | None = None
    pending_scheduled_for: AwareDatetime | None = None
