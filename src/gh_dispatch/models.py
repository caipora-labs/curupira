"""Validated models used at CLI and application boundaries."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from string import Template
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PROMPT_FIELDS = frozenset(
    {
        "repo",
        "issue_number",
        "issue_title",
        "issue_body",
        "issue_url",
        "pull_request_number",
        "pull_request_title",
        "pull_request_body",
        "pull_request_url",
        "pull_request_is_draft",
        "pull_request_head_ref",
        "pull_request_base_ref",
        "task_type",
        "task_number",
        "task_title",
        "task_body",
        "task_url",
    }
)
DEFAULT_ISSUE_JSON_FIELDS = ("number", "title", "body", "url", "state", "labels")


def _validate_prompt_template(value: str) -> str:
    if not value.strip():
        raise ValueError("prompt must not be empty")

    template = Template(value)
    if not template.is_valid():
        raise ValueError("prompt contains an invalid template placeholder")

    unknown = set(template.get_identifiers()) - PROMPT_FIELDS
    if unknown:
        allowed = ", ".join(sorted(PROMPT_FIELDS))
        raise ValueError(
            f"unsupported prompt placeholder(s): {', '.join(sorted(unknown))}; "
            f"available placeholders: {allowed}"
        )
    return value


class AgentSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    prompt: str = Field(min_length=1)
    pull_request_prompt: str | None = None

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        return _validate_prompt_template(value)

    @field_validator("pull_request_prompt")
    @classmethod
    def validate_pull_request_prompt(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_prompt_template(value)


class CodingAgentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Literal["opencode", "codex", "claude", "cursor"] = "opencode"
    model: str | None = None
    agent: str | None = None
    effort: str | None = None

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("model must not be empty when provided")
        return value

    @field_validator("agent", "effort")
    @classmethod
    def validate_optional_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("agent and effort must not be empty when provided")
        return value

    @model_validator(mode="after")
    def validate_provider_options(self) -> CodingAgentProfile:
        if self.provider == "opencode" and self.model is not None and "/" not in self.model:
            raise ValueError("OpenCode model must use the provider/model format")
        if self.provider == "cursor" and self.effort is not None:
            raise ValueError("the Cursor CLI provider does not support the effort option")
        if self.provider == "cursor" and self.agent not in {None, "agent", "ask", "plan"}:
            raise ValueError("Cursor CLI agent mode must be 'agent', 'ask' or 'plan'")
        return self


def _default_coding_agent_profiles() -> dict[str, CodingAgentProfile]:
    return {"opencode": CodingAgentProfile()}


class CodingAgentsSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    default: str = "opencode"
    profiles: dict[str, CodingAgentProfile] = Field(default_factory=_default_coding_agent_profiles)

    @field_validator("default")
    @classmethod
    def validate_default_profile_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("default coding agent profile must not be empty")
        return value


class RepositoryWorkspaceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    repo: str = Field(min_length=3)
    path: Path | None = None
    prompt: str | None = None
    coding_agent: str | None = None

    @field_validator("repo")
    @classmethod
    def validate_repo(cls, value: str) -> str:
        parts = value.split("/")
        if (
            len(parts) != 2
            or any(part in {".", ".."} for part in parts)
            or re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value) is None
        ):
            raise ValueError("repo must use the owner/repository format")
        return value

    @field_validator("path")
    @classmethod
    def expand_path(cls, value: Path | None) -> Path | None:
        if value is None:
            return None
        return value.expanduser()

    @field_validator("prompt")
    @classmethod
    def validate_prompt_override(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_prompt_template(value)

    @field_validator("coding_agent")
    @classmethod
    def validate_coding_agent_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("coding_agent profile name must not be empty")
        return value

    def workspace_path(self, workspace_dir: Path) -> Path:
        if self.path is not None:
            return self.path
        owner, name = self.repo.split("/", maxsplit=1)
        return workspace_dir / owner / name


class RepositorySettings(RepositoryWorkspaceSettings):
    query: str = Field(min_length=1)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be empty")
        return value


class CronJobSettings(RepositoryWorkspaceSettings):
    id: str = Field(min_length=1)
    schedule: str = Field(min_length=1)
    timezone: str = "UTC"
    start_date: datetime | None = None
    end_date: datetime | None = None
    prompt: str = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if re.fullmatch(r"[A-Za-z0-9_.-]+", value) is None:
            raise ValueError("cron job id must contain only letters, digits, '.', '_' or '-'")
        return value

    @field_validator("schedule")
    @classmethod
    def validate_schedule(cls, value: str) -> str:
        if len(value.split()) != 5 or not croniter.is_valid(value):
            raise ValueError("schedule must be a valid five-field cron expression")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError) as error:
            raise ValueError(f"unknown timezone: {value}") from error
        return value

    @model_validator(mode="after")
    def validate_schedule_window(self) -> CronJobSettings:
        timezone = ZoneInfo(self.timezone)
        for field_name in ("start_date", "end_date"):
            value = getattr(self, field_name)
            if value is None:
                continue
            normalized = (
                value.replace(tzinfo=timezone)
                if value.tzinfo is None
                else value.astimezone(timezone)
            )
            object.__setattr__(self, field_name, normalized)
        if self.start_date is not None and self.end_date is not None:
            if self.end_date < self.start_date:
                raise ValueError("end_date must be greater than or equal to start_date")
        if self.prompt is not None:
            _validate_prompt_template(self.prompt)
        return self

    def repository_settings(self) -> RepositoryWorkspaceSettings:
        return RepositoryWorkspaceSettings(
            repo=self.repo,
            path=self.path,
            prompt=self.prompt,
            coding_agent=self.coding_agent,
        )


class CoreSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_active_tasks: int = Field(default=1, ge=1)
    workspace_dir: Path = Field(default=Path("~/.gh-dispatch/workspaces"))
    state_db_path: Path = Field(default=Path("~/.gh-dispatch/state.sqlite3"))

    @field_validator("workspace_dir", mode="before")
    @classmethod
    def expand_workspace_dir(cls, value: str | Path) -> Path:
        return Path(value).expanduser()

    @field_validator("state_db_path", mode="before")
    @classmethod
    def expand_state_db_path(cls, value: str | Path) -> Path:
        return Path(value).expanduser()


class RepositoryWatcherSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    poll_interval_seconds: float = Field(default=30.0, gt=0)
    batch_size: int = Field(default=100, ge=1, le=1000)
    repositories: list[RepositorySettings] = Field(min_length=1)


class CronWatcherSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    poll_interval_seconds: float = Field(default=1.0, gt=0, le=60)
    jobs: list[CronJobSettings] = Field(min_length=1)


class WatchersSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    issues: RepositoryWatcherSettings
    pull_requests: RepositoryWatcherSettings | None = None
    cron: CronWatcherSettings | None = None


class GhIssueSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    repo: str
    query: str
    limit: int = Field(default=1, ge=1, le=1000)


class GhPullRequestSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    repo: str
    query: str
    limit: int = Field(default=1, ge=1, le=1000)


class GhRepositoryCloneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    repo: str
    destination: Path


class GhRepositoryCheckout(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    repo: str
    path: Path
    cloned: bool


class GhLabel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    name: str


class GhIssue(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    number: int
    title: str
    body: str | None = None
    url: str
    state: str | None = None
    labels: list[GhLabel] = Field(default_factory=list)


class GhPullRequest(GhIssue):
    model_config = ConfigDict(extra="ignore", frozen=True, populate_by_name=True)

    is_draft: bool | None = Field(default=None, validation_alias="isDraft")
    head_ref_name: str | None = Field(default=None, validation_alias="headRefName")
    base_ref_name: str | None = Field(default=None, validation_alias="baseRefName")


class PromptContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    repo: str
    issue_number: str
    issue_title: str
    issue_body: str
    issue_url: str
    pull_request_number: str
    pull_request_title: str
    pull_request_body: str
    pull_request_url: str
    pull_request_is_draft: str
    pull_request_head_ref: str
    pull_request_base_ref: str
    task_type: str
    task_number: str
    task_title: str
    task_body: str
    task_url: str


class CodingTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cwd: Path
    message: str = Field(min_length=1)
    model: str | None = None
    agent: str | None = None
    effort: str | None = None
    session_id: str | None = None


class CommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    executable: str = Field(min_length=1)
    arguments: tuple[str, ...] = ()
    cwd: Path | None = None
    timeout: float | None = Field(default=30.0, gt=0)
    capture_output: bool = True


class ProcessResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    returncode: int
    stdout: str = ""
    stderr: str = ""


class SelectedTask(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task_type: Literal["issue", "pull_request", "cron"]
    repository: RepositoryWorkspaceSettings
    number: int
    title: str
    body: str | None = None
    url: str
    workspace_path: Path
    is_draft: bool | None = None
    head_ref_name: str | None = None
    base_ref_name: str | None = None
    cron_job_id: str | None = None
    scheduled_for: datetime | None = None


class RunningCodingSession(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    task: SelectedTask
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    provider: str = Field(default="opencode", min_length=1)
    model: str | None = None
    agent: str | None = None
    effort: str | None = None


class CronRunState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str = Field(min_length=1)
    created_at: datetime
    last_execution_at: datetime | None = None
    last_scheduled_for: datetime | None = None
    pending_scheduled_for: datetime | None = None


class DispatchOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    selected: SelectedTask | None
    process: ProcessResult | None = None
