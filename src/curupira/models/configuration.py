"""Discriminated automation configuration and global execution settings."""

from datetime import datetime
from pathlib import Path
from string import Template
from typing import Annotated, ClassVar, Literal
from zoneinfo import ZoneInfo

from croniter import croniter
from pydantic import AnyHttpUrl, Field, field_validator, model_validator

from curupira.models.azure import AzurePullRequestStatus
from curupira.models.base import (
    AzureRepository,
    BoundedLimit,
    GitHubRepository,
    Identifier,
    NonEmptyString,
    OutputLimit,
    PositiveSeconds,
    RelativeScriptPath,
    TimezoneName,
    ValidatedModel,
)
from curupira.models.profiles import CliProfile, OpenCodeCliProfile

COMMON_PROMPT_FIELDS = frozenset(
    {"repo", "automation_id", "task_type", "task_number", "task_title", "task_body", "task_url"}
)
ISSUE_PROMPT_FIELDS = frozenset({"issue_number", "issue_title", "issue_body", "issue_url"})
PULL_REQUEST_PROMPT_FIELDS = frozenset(
    {
        "pull_request_number",
        "pull_request_title",
        "pull_request_body",
        "pull_request_url",
        "pull_request_is_draft",
        "pull_request_head_ref",
        "pull_request_base_ref",
    }
)


class PollingSettings(ValidatedModel):
    """Global discovery intervals and GitHub query size.

    Attributes:
        poll_interval_seconds: Delay between discovery polls, in seconds.
        batch_size: Maximum number of GitHub items fetched by one poll.
        cron_poll_interval_seconds: Maximum delay between cron schedule checks.
    """

    poll_interval_seconds: PositiveSeconds = 30.0
    batch_size: BoundedLimit = 100
    cron_poll_interval_seconds: Annotated[PositiveSeconds, Field(le=60)] = 1.0


class ExecutionSettings(ValidatedModel):
    """Shared scheduling, workspace, persistence, and process limits.

    Attributes:
        max_active_tasks: Maximum number of coding-agent tasks running concurrently.
        max_pending_tasks: Maximum number of discovered tasks waiting to run.
        workspace_dir: Default directory for repository checkouts and worktrees.
        state_db_path: SQLite database path for durable task and schedule state.
        otlp_endpoint: Optional OTLP/HTTP endpoint for task trace export.
        task_timeout_seconds: Optional time limit for one coding-agent task.
        max_output_bytes: Maximum captured output per subprocess stream.
        polling: Discovery polling intervals and fetch limits.
    """

    max_active_tasks: BoundedLimit = 1
    max_pending_tasks: Annotated[int, Field(strict=True, ge=1, le=10000)] = 100
    workspace_dir: Path = Field(default_factory=lambda: Path("~/.curupira/workspaces"))
    state_db_path: Path = Field(default_factory=lambda: Path("~/.curupira/state.sqlite3"))
    otlp_endpoint: AnyHttpUrl | None = None
    task_timeout_seconds: PositiveSeconds | None = None
    max_output_bytes: OutputLimit = 1_000_000
    polling: PollingSettings = Field(default_factory=PollingSettings)

    @field_validator("workspace_dir", "state_db_path", mode="before")
    @classmethod
    def expand_path(cls, value: str | Path) -> Path:
        """Expand user-relative execution paths."""
        return Path(value).expanduser()


class CodingAgentDefaults(ValidatedModel):
    """Profile reference and timezone inherited by automation definitions.

    Attributes:
        profile: Name of the CLI profile used when an automation does not override it.
        timezone: IANA timezone inherited by cron automations without their own timezone.
    """

    profile: Identifier = "opencode"
    timezone: TimezoneName = "UTC"


class AutomationConfigurationBase(ValidatedModel):
    """Shared options for one automation, keyed by its enclosing TOML table name.

    Subclasses declare ``prompt_fields``, the placeholders their trigger adds to
    ``COMMON_PROMPT_FIELDS``; prompts using any other placeholder are rejected.

    Attributes:
        repo: Repository identifier whose format depends on the trigger type.
        path: Optional base checkout path; relative paths are resolved from the TOML file.
        setup_script: Optional repository-relative script run after a fresh clone.
        checkout: Whether tasks use isolated worktrees or the shared checkout.
        prompt: Template sent to the selected coding-agent CLI.
        profile: Optional named CLI profile overriding the configured default.
    """

    prompt_fields: ClassVar[frozenset[str]] = frozenset()

    repo: NonEmptyString
    path: Path | None = None
    setup_script: RelativeScriptPath | None = None
    checkout: Literal["worktree", "main"] = "worktree"
    prompt: str
    profile: Identifier | None = None

    @field_validator("path")
    @classmethod
    def expand_path(cls, value: Path | None) -> Path | None:
        """Expand the optional user-relative workspace override."""
        return value.expanduser() if value is not None else None

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        """Reject empty prompts, invalid placeholders, and fields this trigger lacks."""
        if not value.strip():
            raise ValueError("prompt must not be empty")
        template = Template(value)
        if not template.is_valid():
            raise ValueError("prompt contains an invalid template placeholder")
        unknown = set(template.get_identifiers()) - COMMON_PROMPT_FIELDS - cls.prompt_fields
        if unknown:
            raise ValueError(f"unsupported prompt placeholders: {sorted(unknown)}")
        return value


class IssueAutomationConfiguration(AutomationConfigurationBase):
    """Discover issues matching a GitHub Search query.

    Attributes:
        trigger_type: Discriminator selecting GitHub issue discovery.
        repo: GitHub repository in ``owner/repository`` form.
        query: GitHub Search query used to select matching issues.
    """

    prompt_fields: ClassVar[frozenset[str]] = ISSUE_PROMPT_FIELDS

    trigger_type: Literal["issue"] = "issue"
    repo: GitHubRepository
    query: NonEmptyString


class PullRequestAutomationConfiguration(AutomationConfigurationBase):
    """Discover pull requests matching a GitHub Search query.

    Attributes:
        trigger_type: Discriminator selecting GitHub CLI pull-request discovery.
        repo: GitHub repository in ``owner/repository`` form.
        query: GitHub Search query used to select matching pull requests.
        jq: Optional ``gh --jq`` filter applied to the listed pull requests.
    """

    prompt_fields: ClassVar[frozenset[str]] = PULL_REQUEST_PROMPT_FIELDS

    trigger_type: Literal["github-cli-pull-requests"] = "github-cli-pull-requests"
    repo: GitHubRepository
    query: NonEmptyString
    jq: NonEmptyString | None = None


class AzurePullRequestAutomationConfiguration(AutomationConfigurationBase):
    """Discover Azure DevOps pull requests through the Azure CLI.

    Attributes:
        trigger_type: Discriminator selecting Azure CLI pull-request discovery.
        repo: Azure DevOps repository in ``organization/project/repository`` form.
        status: Azure DevOps pull-request status filter passed to ``az repos pr list``.
        source_branch: Optional source branch filter.
        target_branch: Optional target branch filter.
    """

    prompt_fields: ClassVar[frozenset[str]] = PULL_REQUEST_PROMPT_FIELDS

    trigger_type: Literal["azure-cli-pull-requests"] = "azure-cli-pull-requests"
    repo: AzureRepository
    status: AzurePullRequestStatus = "active"
    source_branch: NonEmptyString | None = None
    target_branch: NonEmptyString | None = None


class CronAutomationConfiguration(AutomationConfigurationBase):
    """Discover cron occurrences within an optional inclusive date window.

    Attributes:
        trigger_type: Discriminator selecting scheduled occurrences.
        repo: GitHub repository in ``owner/repository`` form.
        schedule: Five-field cron expression defining the occurrence schedule.
        timezone: Optional IANA timezone overriding the inherited default.
        start_date: Optional inclusive earliest occurrence; naive values use the effective timezone.
        end_date: Optional inclusive latest occurrence; naive values use the effective timezone.
    """

    trigger_type: Literal["cron"] = "cron"
    repo: GitHubRepository
    schedule: NonEmptyString
    timezone: TimezoneName | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None

    @field_validator("schedule")
    @classmethod
    def validate_schedule(cls, value: str) -> str:
        """Require a valid five-field cron expression."""
        if len(value.split()) != 5 or not croniter.is_valid(value):
            raise ValueError("schedule must be a valid five-field cron expression")
        return value


AutomationConfiguration = Annotated[
    IssueAutomationConfiguration
    | PullRequestAutomationConfiguration
    | AzurePullRequestAutomationConfiguration
    | CronAutomationConfiguration,
    Field(discriminator="trigger_type"),
]


def default_profiles() -> dict[str, CliProfile]:
    """Provide the minimal default CLI invocation profile."""
    return {"opencode": OpenCodeCliProfile()}


class CodingAgentsSettings(ValidatedModel):
    """Named CLI profiles, inherited defaults, and keyed automation definitions.

    Attributes:
        defaults: Profile and timezone inherited by automations.
        profiles: Non-empty mapping of user-chosen names to provider-specific CLI options.
        automations: Non-empty mapping of user-chosen names to trigger definitions.
    """

    defaults: CodingAgentDefaults = Field(default_factory=CodingAgentDefaults)
    profiles: dict[Identifier, CliProfile] = Field(default_factory=default_profiles, min_length=1)
    automations: dict[Identifier, AutomationConfiguration] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_references_and_windows(self) -> "CodingAgentsSettings":
        """Check profile references and cron date windows."""
        if self.defaults.profile not in self.profiles:
            raise ValueError(f"default profile does not exist: {self.defaults.profile}")
        for name, automation in self.automations.items():
            profile = automation.profile or self.defaults.profile
            if profile not in self.profiles:
                raise ValueError(f"profile {profile!r} for automation {name!r} does not exist")
            if isinstance(automation, CronAutomationConfiguration):
                timezone = ZoneInfo(automation.timezone or self.defaults.timezone)
                start = normalize_date(automation.start_date, timezone)
                end = normalize_date(automation.end_date, timezone)
                if start is not None and end is not None and end < start:
                    raise ValueError(
                        f"end_date must be greater than or equal to start_date: {name}"
                    )
        return self


def normalize_date(value: datetime | None, timezone: ZoneInfo) -> datetime | None:
    """Interpret naive schedule-window dates in the effective timezone."""
    if value is None:
        return None
    return value.replace(tzinfo=timezone) if value.tzinfo is None else value.astimezone(timezone)
