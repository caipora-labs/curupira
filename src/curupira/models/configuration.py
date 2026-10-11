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
    """Global discovery intervals and fetch batch size under ``[settings.polling]``."""

    poll_interval_seconds: Annotated[
        PositiveSeconds,
        Field(
            description=(
                "Base delay in seconds between forge discovery polls when a cycle finds "
                "nothing or fails. Defaults to 30. Must be greater than zero. Empty or "
                "error cycles double this wait up to five minutes (300 seconds); any "
                "discovered task resets the wait to this base (also capped at 300 seconds)."
            )
        ),
    ] = 30.0
    batch_size: Annotated[
        int,
        Field(
            strict=True,
            ge=1,
            le=1000,
            description=(
                "Maximum number of forge items one discovery poll may fetch. Defaults to "
                "100. Must be an integer from 1 through 1000 inclusive. Passed to each "
                "task source's discover call; per-automation deduplication still applies "
                "after the fetch."
            ),
        ),
    ] = 100
    cron_poll_interval_seconds: Annotated[
        PositiveSeconds,
        Field(
            le=60,
            description=(
                "Delay in seconds between cron schedule checks while streaming "
                "occurrences. Defaults to 1. Must be greater than zero and at most 60. "
                "Cron feeds sleep this long after each poll cycle rather than using the "
                "forge poll backoff."
            ),
        ),
    ] = 1.0


class ExecutionSettings(ValidatedModel):
    """Shared scheduling, workspace, persistence, and process limits under ``[settings]``."""

    max_active_tasks: Annotated[
        int,
        Field(
            strict=True,
            ge=1,
            le=1000,
            description=(
                "Maximum number of coding-agent tasks Curupira runs concurrently. Defaults "
                "to 1. Must be an integer from 1 through 1000 inclusive. The scheduler "
                "also keeps checkouts that share a workspace path from overlapping, so "
                'shared ``checkout = "main"`` work still runs one at a time per path.'
            ),
        ),
    ] = 1
    max_pending_tasks: Annotated[
        int,
        Field(
            strict=True,
            ge=1,
            le=10000,
            description=(
                "Maximum number of discovered tasks waiting to run. Defaults to 100. Must "
                "be an integer from 1 through 10000 inclusive. The scheduler stops reading "
                "new feed items while the pending queue is at this limit, and merged task "
                "streams use the same bound as their buffer size."
            ),
        ),
    ] = 100
    workspace_dir: Path = Field(
        default_factory=lambda: Path("~/.curupira/workspaces"),
        description=(
            "Default directory for repository checkouts when a repository alias omits "
            "``path``. Defaults to ``~/.curupira/workspaces``. ``~`` is expanded; when "
            "loaded from TOML, relative paths resolve against the configuration file "
            "directory. Each automation then uses ``workspace_dir/<repository-alias>`` "
            "unless the alias sets its own ``path``."
        ),
    )
    state_db_path: Path = Field(
        default_factory=lambda: Path("~/.curupira/state.sqlite3"),
        description=(
            "SQLite database path for durable state: running coding sessions, cron "
            "schedule state, and state used by triggers. Defaults to "
            "``~/.curupira/state.sqlite3``. ``~`` is expanded; when loaded from TOML, "
            "relative paths resolve against the configuration file directory. An "
            "incompatible existing database raises an error instead of being deleted."
        ),
    )
    otlp_endpoint: AnyHttpUrl | None = Field(
        default=None,
        description=(
            "Optional OTLP/HTTP endpoint URL for exporting per-task OpenTelemetry spans. "
            "Defaults to unset, which disables export and uses a no-op tracer. When set, "
            "must be an HTTP or HTTPS URL passed to the OTLP/HTTP span exporter "
            "(for example ``http://localhost:4318/v1/traces``)."
        ),
    )
    task_timeout_minutes: Annotated[
        PositiveMinutes,
        Field(
            description=(
                "Time limit in minutes for one coding-agent run and its optional setup "
                "script. Defaults to 20. Must be a positive integer. Curupira converts "
                "this value to seconds for subprocess timeouts; exceeding it raises a CLI "
                "timeout for that process."
            )
        ),
    ] = 20
    max_output_bytes: Annotated[
        int,
        Field(
            strict=True,
            ge=1024,
            le=100_000_000,
            description=(
                "Maximum captured bytes retained per subprocess stdout or stderr stream. "
                "Defaults to 1000000 bytes. Must be an integer from 1024 through "
                "100000000 inclusive. Applies to coding-agent runs and setup scripts; "
                "output beyond the limit keeps only the trailing bytes and marks the "
                "result as truncated."
            ),
        ),
    ] = 1_000_000
    polling: PollingSettings = Field(
        default_factory=PollingSettings,
        description=(
            "Nested discovery polling intervals and fetch limits from "
            "``[settings.polling]``. Defaults to ``PollingSettings`` values when the "
            "table is omitted."
        ),
    )

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
    """Local Git checkout identity under ``[repositories.<alias>]``, shared by automations."""

    remote: Annotated[
        NonEmptyString,
        Field(
            description=(
                "Full Git remote URL used for ``git clone``. Required. Accepts "
                "``http://``, ``https://``, ``ssh://``, ``git://``, ``file://``, or "
                "``user@host:path`` forms, without whitespace. Forge discovery identity "
                "(``repo`` on GitHub/Azure automations) is independent of this clone URL."
            )
        ),
    ]
    path: Path | None = Field(
        default=None,
        description=(
            "Optional base checkout path for this repository alias. Defaults to unset, in "
            "which case Curupira uses ``settings.workspace_dir/<alias>``. ``~`` is "
            "expanded; when loaded from TOML, relative paths resolve against the "
            "configuration file directory. Different repository aliases cannot share one "
            "resolved workspace path."
        ),
    )
    setup_script: str | None = Field(
        default=None,
        description=(
            "Optional repository-relative executable run only after a fresh base clone. "
            "Defaults to unset (no setup). Must be a non-empty relative path without "
            "``..`` or absolute/drive roots; validation checks syntax only, not existence. "
            "It runs with the checkout root as cwd, not inside a task worktree; a nonzero "
            "exit prevents the agent from starting and removes the newly cloned checkout."
        ),
    )

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
    """Profile reference and timezone inherited by automation definitions."""

    profile: Identifier = Field(
        default="opencode",
        description=(
            "Name of the CLI profile used when an automation omits ``profile``. "
            "Must be a key in ``agents.profiles`` (enforced by "
            "``AgentsSettings`` and by ``ApplicationSettings.validate_cross_references``). "
            "Default is ``opencode``. Must match the identifier pattern "
            "``^[A-Za-z0-9_-]+$``."
        ),
    )
    timezone: NonEmptyString = Field(
        default="UTC",
        description=(
            "IANA timezone inherited by cron automations that omit their own "
            "``timezone``. Default is ``UTC``. Must name a known IANA zone; "
            "unknown values are rejected."
        ),
    )

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
    """

    trigger_type: NonEmptyString = Field(
        description=(
            "Registered trigger type that selects which configuration model validates "
            "this `[automations.<name>]` table. When `trigger_type` is omitted from TOML, "
            "`parse_automation_configuration` chooses `cron` if the `schedule` key is "
            "present, otherwise `github-issues`."
        )
    )
    repository: Identifier = Field(
        description=(
            "Alias of a `[repositories.<alias>]` entry whose `remote`, optional `path`, "
            "and optional `setup_script` Curupira uses for the Git checkout for this "
            "automation. Must match an existing repository key "
            "(`[A-Za-z0-9_-]+`)."
        )
    )
    checkout: Literal["worktree", "main"] = Field(
        default="worktree",
        description=(
            "`worktree` (default): after `git fetch origin`, each task gets its own "
            "worktree and `curupira/<automation>/<task>` branch from `origin`'s default "
            "branch, removed when the task ends. `main`: runs the agent directly in the "
            "shared checkout with no fetch, pull, or branch switch (the repository is "
            "only cloned if missing)."
        ),
    )
    prompt: str = Field(
        description=(
            "Message template sent to the selected coding-agent CLI. Uses "
            "`string.Template` `${name}` placeholders; must be non-empty and syntactically "
            "valid. When the whole configuration is loaded, Curupira rejects unknown "
            "placeholders against the common set (`repo`, `repository`, `automation_id`, "
            "`task_type`, `task_number`, `task_title`, `task_body`, `task_url`) plus the "
            "trigger's item-model fields. `${repo}` is the forge identity when the "
            "trigger has one; `${repository}` is the checkout alias."
        )
    )
    profile: Identifier | None = Field(
        default=None,
        description=(
            "Optional name of a CLI profile under `[agents.profiles.<name>]`. When "
            "omitted, the automation inherits `[agents.defaults].profile` (default "
            "`opencode`). The chosen name must exist among configured profiles."
        ),
    )

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
    """Shared GitHub GraphQL Search filters for issue and pull-request automations."""

    repo: NonEmptyString = Field(
        description=(
            "GitHub repository identity in `owner/repository` form, compiled into the "
            "GraphQL Search `repo:` qualifier. Must match "
            "`[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+` and must not contain `.` or `..` path "
            "segments. Independent of the checkout `remote` on the repository alias."
        )
    )
    state: GitHubItemState = Field(
        default="open",
        description=(
            "Issue or pull-request state filter compiled into the search query. `open` "
            "(default) adds `is:open`, `closed` adds `is:closed`, and `all` adds no "
            "state qualifier."
        ),
    )
    labels: tuple[NonEmptyString, ...] = Field(
        default=(),
        description=(
            "Labels that must all be present (AND). Each value becomes a `label:` search "
            "qualifier. Defaults to an empty tuple (no label filter). Values containing "
            "whitespace, quotes, colons, or commas are quoted in the query."
        ),
    )
    exclude_labels: tuple[NonEmptyString, ...] = Field(
        default=(),
        description=(
            "Labels that must be absent. Each value becomes a `-label:` search qualifier. "
            "Defaults to an empty tuple (no exclusion filter). Values containing "
            "whitespace, quotes, colons, or commas are quoted in the query."
        ),
    )
    assignee: NonEmptyString | None = Field(
        default=None,
        description=(
            "Assignee search filter. A login or `@me` becomes `assignee:<value>`; the "
            "special values `none` and `any` become `no:assignee` and `assignee:*`. "
            "When omitted, no assignee qualifier is added. Login values containing "
            "whitespace, quotes, colons, or commas are quoted in the query."
        ),
    )
    author: NonEmptyString | None = Field(
        default=None,
        description=(
            "Issue or pull-request author login compiled as `author:<value>`. When "
            "omitted, no author qualifier is added. Values containing whitespace, quotes, "
            "colons, or commas are quoted in the query."
        ),
    )
    milestone: NonEmptyString | None = Field(
        default=None,
        description=(
            "Milestone title compiled as `milestone:<value>`. When omitted, no milestone "
            "qualifier is added. Values containing whitespace, quotes, colons, or commas "
            "are quoted in the query."
        ),
    )
    project: NonEmptyString | None = Field(
        default=None,
        description=(
            "GitHub project search qualifier compiled as `project:<value>`. Use the "
            "project's `owner/number` form expected by GitHub Search. When omitted, no "
            "project qualifier is added. Values containing whitespace, quotes, colons, "
            "or commas are quoted in the query."
        ),
    )
    sort: GitHubSort = Field(
        default="created-asc",
        description=(
            "Search sort qualifier appended as `sort:<value>`. Accepted values are "
            "`created-asc`, `created-desc`, `updated-asc`, `updated-desc`, "
            "`comments-asc`, and `comments-desc`. Defaults to `created-asc`."
        ),
    )

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
    """Discover GitHub issues through typed filters compiled to GraphQL Search.

    Selected by ``trigger_type = "github-issues"``.
    """

    trigger_type: NonEmptyString = Field(
        default="github-issues",
        description="Must be `github-issues` for this model.",
    )
    linked_pull_request: bool | None = Field(
        default=None,
        description=(
            "When `true`, require a linked closing pull request (`linked:pr`). When "
            "`false`, exclude issues that have one (`-linked:pr`). When omitted, no "
            "linked-PR qualifier is added."
        ),
    )


class PullRequestAutomationConfiguration(GitHubAutomationConfiguration):
    """Discover GitHub pull requests through typed Search filters and merge post-filters.

    Selected by ``trigger_type = "github-pull-requests"``.
    """

    trigger_type: NonEmptyString = Field(
        default="github-pull-requests",
        description="Must be `github-pull-requests` for this model.",
    )
    draft: bool | None = Field(
        default=None,
        description=(
            "When `true`, require draft pull requests (`draft:true`). When `false`, "
            "require ready-for-review pull requests (`draft:false`). When omitted, no "
            "draft qualifier is added."
        ),
    )
    base: NonEmptyString | None = Field(
        default=None,
        description=(
            "Base branch name compiled as `base:<value>`. When omitted, no base-branch "
            "qualifier is added. Values containing whitespace, quotes, colons, or commas "
            "are quoted in the query."
        ),
    )
    head: NonEmptyString | None = Field(
        default=None,
        description=(
            "Head branch name compiled as `head:<value>`. When omitted, no head-branch "
            "qualifier is added. Values containing whitespace, quotes, colons, or commas "
            "are quoted in the query."
        ),
    )
    review: GitHubReviewFilter | None = Field(
        default=None,
        description=(
            "Review-state search qualifier compiled as `review:<value>`. Accepted values "
            "are `none`, `required`, `approved`, and `changes_requested`. When omitted, "
            "no review qualifier is added."
        ),
    )
    ci_status: GitHubCiStatus | None = Field(
        default=None,
        description=(
            "Commit status search qualifier compiled as `status:<value>` (not "
            "`ci_status:`). Accepted values are `success`, `failure`, and `pending`. "
            "When omitted, no status qualifier is added."
        ),
    )
    linked_issue: bool | None = Field(
        default=None,
        description=(
            "When `true`, require a linked closing issue (`linked:issue`). When `false`, "
            "exclude pull requests that have one (`-linked:issue`). When omitted, no "
            "linked-issue qualifier is added."
        ),
    )
    mergeable: bool | None = Field(
        default=None,
        description=(
            "Post-filter applied after GraphQL fetch because Search cannot express it. "
            "`true` keeps only pull requests whose GraphQL `mergeable` is `MERGEABLE`; "
            "`false` keeps only `CONFLICTING`. When omitted, mergeability is not "
            "filtered."
        ),
    )
    merge_state: tuple[GitHubMergeStateStatus, ...] = Field(
        default=(),
        description=(
            "Optional post-filter on GraphQL `mergeStateStatus`. When empty (default), "
            "no merge-state filter is applied. When one or more values are set, the "
            "pull request is kept only if its status is in the tuple. Accepted values "
            "are `BEHIND`, `BLOCKED`, `CLEAN`, `DIRTY`, `DRAFT`, `HAS_HOOKS`, "
            "`UNKNOWN`, and `UNSTABLE`."
        ),
    )


class AzurePullRequestAutomationConfiguration(AutomationConfigurationBase):
    """Discover Azure DevOps pull requests through the Azure CLI.

    Selected by ``trigger_type = "azure-cli-pull-requests"``.
    """

    trigger_type: NonEmptyString = Field(
        default="azure-cli-pull-requests",
        description="Must be `azure-cli-pull-requests` for this model.",
    )
    repo: NonEmptyString = Field(
        description=(
            "Azure DevOps repository identity in `organization/project/repository` form, "
            "split into `--organization`, `--project`, and `--repository` for "
            "`az repos pr list`. A bare organization name becomes "
            "`https://dev.azure.com/<organization>` via `organization_url`; an `http://` "
            "or `https://` value is passed through. `--top` comes from the discovery "
            "poll limit. Must match three `[A-Za-z0-9_.-]+` segments and must not "
            "contain `.` or `..` path segments. Independent of the checkout `remote` on "
            "the repository alias."
        )
    )
    status: AzurePullRequestStatus = Field(
        default="active",
        description=(
            "Pull-request status filter passed to `az repos pr list --status`. Accepted "
            "values are `active` (default), `completed`, `abandoned`, and `all`."
        ),
    )
    source_branch: NonEmptyString | None = Field(
        default=None,
        description=(
            "Optional source branch name passed as `--source-branch` to "
            "`az repos pr list`. When omitted, Azure CLI lists pull requests from any "
            "source branch."
        ),
    )
    target_branch: NonEmptyString | None = Field(
        default=None,
        description=(
            "Optional target branch name passed as `--target-branch` to "
            "`az repos pr list`. When omitted, Azure CLI lists pull requests into any "
            "target branch."
        ),
    )

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

    Selected by ``trigger_type = "trello-cli-cards"``.
    """

    trigger_type: NonEmptyString = Field(
        default="trello-cli-cards",
        description="Must be `trello-cli-cards` for this model.",
    )
    board_id: NonEmptyString = Field(
        description=(
            "Trello board ID passed to `trello cards list --board`. Curupira lists cards "
            "on this board and keeps each card's string ID for task identity and prompt "
            "placeholders."
        )
    )
    list_ids: tuple[NonEmptyString, ...] | None = Field(
        default=None,
        description=(
            "Optional board list IDs that restrict discovery. When set, only open cards "
            "whose `idList` is in the tuple are scheduled. When omitted (`null`), all "
            "open cards on the board are eligible. Closed cards are always excluded "
            "after listing."
        ),
    )


class CronAutomationConfiguration(AutomationConfigurationBase):
    """Produce local cron occurrences within an optional inclusive date window.

    Selected by ``trigger_type = "cron"``.
    """

    trigger_type: NonEmptyString = Field(
        default="cron",
        description="Must be `cron` for this model.",
    )
    schedule: NonEmptyString = Field(
        description=(
            "Five-field cron expression (minute hour day-of-month month day-of-week). "
            "Must be valid for `croniter`; six-field expressions are rejected. Ticks "
            "missed while Curupira was not running coalesce into the latest due "
            "occurrence, and only one occurrence is pending at a time."
        )
    )
    timezone: NonEmptyString | None = Field(
        default=None,
        description=(
            "Optional IANA timezone for evaluating the schedule and naive date-window "
            "bounds. When omitted, resolution fills `[agents.defaults].timezone` "
            "(default `UTC`). Unknown zone names are rejected."
        ),
    )
    start_date: datetime | None = Field(
        default=None,
        description=(
            "Optional inclusive earliest occurrence. Naive values are interpreted in the "
            "effective timezone; aware values are converted to that zone. When omitted, "
            "the window starts at the automation's first recorded schedule state "
            "(`created_at`)."
        ),
    )
    end_date: datetime | None = Field(
        default=None,
        description=(
            "Optional inclusive latest occurrence. Naive values are interpreted in the "
            "effective timezone; aware values are converted to that zone. When both "
            "`start_date` and `end_date` are set, `end_date` must be greater than or "
            'equal to `start_date`. When omitted, there is no end bound beyond "now".'
        ),
    )

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
    """Named CLI profiles and inherited defaults for coding agents."""

    defaults: AgentDefaults = Field(
        default_factory=AgentDefaults,
        description=(
            "``[agents.defaults]`` profile name and timezone inherited by "
            "automations that do not override them. The default profile must "
            "exist in ``profiles``."
        ),
    )
    profiles: dict[Identifier, CliProfile] = Field(
        default_factory=default_profiles,
        min_length=1,
        description=(
            "Non-empty mapping of user-chosen profile names to "
            "provider-specific CLI options under ``[agents.profiles.<name>]``. "
            "Keys must match ``^[A-Za-z0-9_-]+$``. At least one profile is "
            "required; when omitted, Curupira supplies a single ``opencode`` "
            "profile. ``defaults.profile`` must name an entry in this mapping."
        ),
    )

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
