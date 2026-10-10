"""Discriminated automation configuration and global execution settings."""

import re
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from string import Template
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from pydantic import (
    AnyHttpUrl,
    BeforeValidator,
    Field,
    SerializeAsAny,
    field_validator,
    model_validator,
)

from curupira.models.azure import AzurePullRequestStatus
from curupira.models.base import (
    Identifier,
    NonEmptyString,
    PositiveMinutes,
    PositiveSeconds,
    ValidatedModel,
)
from curupira.models.profiles import CliProfile, OpenCodeCliProfile

COMMON_PROMPT_FIELDS = frozenset(
    {
        "repo",
        "repository",
        "automation_id",
        "task_type",
        "task_number",
        "task_title",
        "task_body",
        "task_url",
    }
)

GitHubItemState = Literal["open", "closed", "all"]
GitHubSort = Literal[
    "created-asc",
    "created-desc",
    "updated-asc",
    "updated-desc",
    "comments-asc",
    "comments-desc",
]
GitHubReviewFilter = Literal["none", "required", "approved", "changes_requested"]
GitHubCiStatus = Literal["success", "failure", "pending"]
GitHubMergeStateStatus = Literal[
    "BEHIND",
    "BLOCKED",
    "CLEAN",
    "DIRTY",
    "DRAFT",
    "HAS_HOOKS",
    "UNKNOWN",
    "UNSTABLE",
]


def validate_timezone(value: str) -> str:
    """Validate an IANA timezone without inventing a fallback."""
    try:
        ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError) as error:
        raise ValueError(f"unknown timezone: {value}") from error
    return value


def validate_setup_script(value: str | None) -> str | None:
    """Require an optional repository-relative script path without traversal."""
    if value is None:
        return None
    if not value.strip():
        raise ValueError("setup_script must not be empty")
    path = Path(value)
    posix_path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if (
        path.is_absolute()
        or posix_path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.root)
        or ".." in path.parts
        or ".." in windows_path.parts
    ):
        raise ValueError("setup_script must be a relative path without '..'")
    return value


def validate_git_remote(value: str) -> str:
    """Require a full Git remote URL (HTTPS, SSH, or git protocol)."""
    remote = value.strip()
    if not remote or any(character.isspace() for character in remote):
        raise ValueError("remote must be a non-empty Git URL without whitespace")
    if remote.startswith(("http://", "https://", "ssh://", "git://", "file://")):
        return remote
    if re.fullmatch(r"[^/@\s]+@[^:\s]+:\S+", remote) is not None:
        return remote
    raise ValueError(
        "remote must be a full Git URL (https://, ssh://, git://, file://, or user@host:path)"
    )


class PollingSettings(ValidatedModel):
    """Global discovery intervals and fetch batch size.

    Attributes:
        poll_interval_seconds: Delay between discovery polls, in seconds.
        batch_size: Maximum number of forge items fetched by one poll.
        cron_poll_interval_seconds: Maximum delay between cron schedule checks.
    """

    poll_interval_seconds: PositiveSeconds = 30.0
    batch_size: Annotated[int, Field(strict=True, ge=1, le=1000)] = 100
    cron_poll_interval_seconds: Annotated[PositiveSeconds, Field(le=60)] = 1.0


class ExecutionSettings(ValidatedModel):
    """Shared scheduling, workspace, persistence, and process limits.

    Attributes:
        max_active_tasks: Maximum number of coding-agent tasks running concurrently.
        max_pending_tasks: Maximum number of discovered tasks waiting to run.
        workspace_dir: Default directory for repository checkouts and worktrees.
        state_db_path: SQLite database path for durable task and schedule state.
        otlp_endpoint: Optional OTLP/HTTP endpoint for task trace export.
        task_timeout_minutes: Time limit for one coding-agent task, in minutes.
        max_output_bytes: Maximum captured output per subprocess stream.
        polling: Discovery polling intervals and fetch limits.
    """

    max_active_tasks: Annotated[int, Field(strict=True, ge=1, le=1000)] = 1
    max_pending_tasks: Annotated[int, Field(strict=True, ge=1, le=10000)] = 100
    workspace_dir: Path = Field(default_factory=lambda: Path("~/.curupira/workspaces"))
    state_db_path: Path = Field(default_factory=lambda: Path("~/.curupira/state.sqlite3"))
    otlp_endpoint: AnyHttpUrl | None = None
    task_timeout_minutes: PositiveMinutes = 20
    max_output_bytes: Annotated[int, Field(strict=True, ge=1024, le=100_000_000)] = 1_000_000
    polling: PollingSettings = Field(default_factory=PollingSettings)

    @property
    def task_timeout_seconds(self) -> float:
        """Convert the configured minute limit to seconds for process runners."""
        return float(self.task_timeout_minutes) * 60.0

    @field_validator("workspace_dir", "state_db_path", mode="before")
    @classmethod
    def expand_path(cls, value: str | Path) -> Path:
        """Expand user-relative execution paths."""
        return Path(value).expanduser()


class RepositoryConfiguration(ValidatedModel):
    """Local Git checkout identity shared by one or more automations.

    Attributes:
        remote: Full Git remote URL used for ``git clone``.
        path: Optional base checkout path; relative paths resolve from the TOML file.
        setup_script: Optional repository-relative script run after a fresh clone.
    """

    remote: NonEmptyString
    path: Path | None = None
    setup_script: str | None = None

    @field_validator("remote")
    @classmethod
    def validate_remote(cls, value: str) -> str:
        """Require a full Git remote URL."""
        return validate_git_remote(value)

    @field_validator("setup_script")
    @classmethod
    def validate_setup_script_field(cls, value: str | None) -> str | None:
        """Validate the optional setup script path."""
        return validate_setup_script(value)

    @field_validator("path")
    @classmethod
    def expand_path(cls, value: Path | None) -> Path | None:
        """Expand the optional user-relative workspace override."""
        return value.expanduser() if value is not None else None


class AgentDefaults(ValidatedModel):
    """Profile reference and timezone inherited by automation definitions.

    Attributes:
        profile: Name of the CLI profile used when an automation does not override it.
        timezone: IANA timezone inherited by cron automations without their own timezone.
    """

    profile: Identifier = "opencode"
    timezone: NonEmptyString = "UTC"

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        """Require a known IANA timezone."""
        return validate_timezone(value)


# Compatibility alias while documentation and imports settle.
CodingAgentDefaults = AgentDefaults


class AutomationConfigurationBase(ValidatedModel):
    """Shared options for one automation, keyed by its enclosing TOML table name.

    Trigger plugins extend this model and give ``trigger_type`` a default equal to
    their registered type.

    Attributes:
        trigger_type: Registered trigger type selecting the configuration model.
        repository: Alias of a ``[repositories.<alias>]`` entry used for Git checkout.
        checkout: Whether tasks use isolated worktrees or the shared checkout.
        prompt: Template sent to the selected coding-agent CLI.
        profile: Optional named CLI profile overriding the configured default.
    """

    trigger_type: NonEmptyString
    repository: Identifier
    checkout: Literal["worktree", "main"] = "worktree"
    prompt: str
    profile: Identifier | None = None

    @field_validator("prompt")
    @classmethod
    def validate_prompt_syntax(cls, value: str) -> str:
        """Reject empty prompts and invalid template placeholders."""
        if not value.strip():
            raise ValueError("prompt must not be empty")
        if not Template(value).is_valid():
            raise ValueError("prompt contains an invalid template placeholder")
        return value


class GitHubAutomationConfiguration(AutomationConfigurationBase):
    """Shared GitHub GraphQL discovery filters for issues and pull requests.

    Attributes:
        repo: GitHub ``owner/repository`` identity used for GraphQL search.
        state: Open/closed/all filter compiled into the search query.
        labels: Labels that must all be present (AND).
        exclude_labels: Labels that must be absent.
        assignee: Login, ``@me``, ``none``, or ``any``.
        author: Issue or pull-request author login.
        milestone: Milestone title filter.
        project: GitHub project qualifier (``owner/number``).
        sort: Search sort qualifier.
    """

    repo: NonEmptyString
    state: GitHubItemState = "open"
    labels: tuple[NonEmptyString, ...] = ()
    exclude_labels: tuple[NonEmptyString, ...] = ()
    assignee: NonEmptyString | None = None
    author: NonEmptyString | None = None
    milestone: NonEmptyString | None = None
    project: NonEmptyString | None = None
    sort: GitHubSort = "created-asc"

    @field_validator("repo")
    @classmethod
    def validate_repository(cls, value: str) -> str:
        """Require the owner/repository format without traversal segments."""
        if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value) is None:
            raise ValueError("repo must use the owner/repository format")
        if any(part in {".", ".."} for part in value.split("/")):
            raise ValueError("repo must not contain traversal segments")
        return value


class IssueAutomationConfiguration(GitHubAutomationConfiguration):
    """Discover GitHub issues through typed filters compiled to GraphQL search.

    Attributes:
        linked_pull_request: When set, require or exclude a linked closing PR.
    """

    trigger_type: NonEmptyString = "github-issues"
    linked_pull_request: bool | None = None


class PullRequestAutomationConfiguration(GitHubAutomationConfiguration):
    """Discover GitHub pull requests through typed filters and merge post-filters.

    Attributes:
        draft: When set, require draft or ready-for-review pull requests.
        base: Base branch name filter.
        head: Head branch name filter.
        review: Review-state search qualifier.
        ci_status: Commit-status search qualifier.
        linked_issue: When set, require or exclude a linked closing issue.
        mergeable: Post-filter on GraphQL ``mergeable`` (true=MERGEABLE, false=CONFLICTING).
        merge_state: Optional post-filter on GraphQL ``mergeStateStatus`` values.
    """

    trigger_type: NonEmptyString = "github-pull-requests"
    draft: bool | None = None
    base: NonEmptyString | None = None
    head: NonEmptyString | None = None
    review: GitHubReviewFilter | None = None
    ci_status: GitHubCiStatus | None = None
    linked_issue: bool | None = None
    mergeable: bool | None = None
    merge_state: tuple[GitHubMergeStateStatus, ...] = ()


class AzurePullRequestAutomationConfiguration(AutomationConfigurationBase):
    """Discover Azure DevOps pull requests through the Azure CLI.

    Attributes:
        repo: Azure DevOps repository in ``organization/project/repository`` form.
        status: Azure DevOps pull-request status filter passed to ``az repos pr list``.
        source_branch: Optional source branch filter.
        target_branch: Optional target branch filter.
    """

    trigger_type: NonEmptyString = "azure-cli-pull-requests"
    repo: NonEmptyString
    status: AzurePullRequestStatus = "active"
    source_branch: NonEmptyString | None = None
    target_branch: NonEmptyString | None = None

    @field_validator("repo")
    @classmethod
    def validate_repository(cls, value: str) -> str:
        """Require the organization/project/repository format without traversal."""
        if (
            re.fullmatch(
                r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+",
                value,
            )
            is None
        ):
            raise ValueError("repo must use the organization/project/repository format")
        if any(part in {".", ".."} for part in value.split("/")):
            raise ValueError("repo must not contain traversal segments")
        return value


class TrelloAutomationConfiguration(AutomationConfigurationBase):
    """Discover cards from one Trello board through Scale-Flow's ``trello-cli``.

    Attributes:
        board_id: Trello board ID to query.
        list_ids: Optional list IDs restricting discovery to selected board lists.
    """

    trigger_type: NonEmptyString = "trello-cli-cards"
    board_id: NonEmptyString
    list_ids: tuple[NonEmptyString, ...] | None = None


class CronAutomationConfiguration(AutomationConfigurationBase):
    """Discover cron occurrences within an optional inclusive date window.

    Attributes:
        schedule: Five-field cron expression defining the occurrence schedule.
        timezone: Optional IANA timezone overriding the inherited default.
        start_date: Optional inclusive earliest occurrence; naive values use the effective timezone.
        end_date: Optional inclusive latest occurrence; naive values use the effective timezone.
    """

    trigger_type: NonEmptyString = "cron"
    schedule: NonEmptyString
    timezone: NonEmptyString | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None

    @field_validator("schedule")
    @classmethod
    def validate_schedule(cls, value: str) -> str:
        """Require a valid five-field cron expression."""
        if len(value.split()) != 5 or not croniter.is_valid(value):
            raise ValueError("schedule must be a valid five-field cron expression")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_optional_timezone(cls, value: str | None) -> str | None:
        """Validate the optional IANA timezone."""
        return validate_timezone(value) if value is not None else None


def parse_automation_configuration(value: object) -> object:
    """Validate an automation table with the model of its registered trigger."""
    if not isinstance(value, dict):
        return value
    from curupira.tasks.registry import get

    trigger_type = value.get("trigger_type")
    if trigger_type is None:
        trigger_type = "cron" if "schedule" in value else "github-issues"
    if not isinstance(trigger_type, str):
        raise ValueError("trigger_type must be a string")
    return get(trigger_type).configuration_model.model_validate(value)


# SerializeAsAny keeps plugin-specific fields when snapshots are dumped and revalidated.
AutomationConfiguration = Annotated[
    SerializeAsAny[AutomationConfigurationBase],
    BeforeValidator(parse_automation_configuration),
]


def default_profiles() -> dict[str, CliProfile]:
    """Provide the minimal default CLI invocation profile."""
    return {"opencode": OpenCodeCliProfile()}


class AgentsSettings(ValidatedModel):
    """Named CLI profiles and inherited defaults for coding agents.

    Attributes:
        defaults: Profile and timezone inherited by automations.
        profiles: Non-empty mapping of user-chosen names to provider-specific CLI options.
    """

    defaults: AgentDefaults = Field(default_factory=AgentDefaults)
    profiles: dict[Identifier, CliProfile] = Field(default_factory=default_profiles, min_length=1)

    @model_validator(mode="after")
    def validate_default_profile(self) -> "AgentsSettings":
        """Require the default profile to exist among configured profiles."""
        if self.defaults.profile not in self.profiles:
            raise ValueError(f"default profile does not exist: {self.defaults.profile}")
        return self


# Compatibility alias for older imports.
CodingAgentsSettings = AgentsSettings


def normalize_date(value: datetime | None, timezone: ZoneInfo) -> datetime | None:
    """Interpret naive schedule-window dates in the effective timezone."""
    if value is None:
        return None
    return value.replace(tzinfo=timezone) if value.tzinfo is None else value.astimezone(timezone)


def forge_identity(configuration: AutomationConfigurationBase, repository_id: str) -> str:
    """Return the forge repository string when present, else the repository alias."""
    repo = getattr(configuration, "repo", None)
    if isinstance(repo, str) and repo:
        return repo
    return repository_id
