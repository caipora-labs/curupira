"""TOML-backed Pydantic Settings and asynchronous configuration loading."""

from __future__ import annotations

import asyncio
from pathlib import Path

from pydantic import Field, ValidationError, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from gh_dispatch.models import (
    AgentSettings,
    CodingAgentsSettings,
    CoreSettings,
    RepositorySettings,
    RepositoryWatcherSettings,
    WatchersSettings,
)


class AppSettings(BaseSettings):
    """Application configuration loaded from a TOML file."""

    model_config = SettingsConfigDict(extra="forbid", validate_default=True)

    agent: AgentSettings
    core: CoreSettings = Field(default_factory=CoreSettings)
    coding_agents: CodingAgentsSettings = Field(default_factory=CodingAgentsSettings)
    watchers: WatchersSettings

    @model_validator(mode="after")
    def validate_repositories(self) -> AppSettings:
        watcher_configs = [self.watchers.issues]
        if self.watchers.pull_requests is not None:
            watcher_configs.append(self.watchers.pull_requests)
        cron_jobs = self.watchers.cron.jobs if self.watchers.cron is not None else []
        cron_job_ids = [job.id for job in cron_jobs]
        if len(cron_job_ids) != len(set(cron_job_ids)):
            raise ValueError("cron job IDs must be unique")
        for watcher in watcher_configs:
            repos = [repository.repo for repository in watcher.repositories]
            if len(repos) != len(set(repos)):
                raise ValueError("repository entries must be unique within each watcher")

        profile_names = set(self.coding_agents.profiles)
        if self.coding_agents.default not in profile_names:
            raise ValueError(
                f"default coding agent profile does not exist: {self.coding_agents.default}"
            )
        for watcher in watcher_configs:
            for repository in watcher.repositories:
                if (
                    repository.coding_agent is not None
                    and repository.coding_agent not in profile_names
                ):
                    raise ValueError(
                        f"coding agent profile {repository.coding_agent!r} "
                        f"for {repository.repo} does not exist"
                    )
        for job in cron_jobs:
            if job.coding_agent is not None and job.coding_agent not in profile_names:
                raise ValueError(
                    f"coding agent profile {job.coding_agent!r} for cron job {job.id!r} "
                    "does not exist"
                )
        return self

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        del env_settings, dotenv_settings, file_secret_settings
        toml_file = settings_cls.model_config.get("toml_file")
        if toml_file is None:
            return (init_settings,)
        return (init_settings, TomlConfigSettingsSource(settings_cls, toml_file=toml_file))


def _load_settings_sync(config_path: Path) -> AppSettings:
    config_path = config_path.expanduser().resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"configuration file not found: {config_path}")

    class FileSettings(AppSettings):
        model_config = SettingsConfigDict(
            toml_file=config_path,
            extra="forbid",
            validate_default=True,
        )

    settings = FileSettings()
    workspace_dir = settings.core.workspace_dir
    if not workspace_dir.is_absolute():
        workspace_dir = config_path.parent / workspace_dir
    workspace_dir = workspace_dir.resolve()

    watchers_to_resolve = [settings.watchers.issues]
    if settings.watchers.pull_requests is not None:
        watchers_to_resolve.append(settings.watchers.pull_requests)

    resolved_watchers: list[RepositoryWatcherSettings] = []
    workspace_paths: dict[Path, str] = {}
    for watcher in watchers_to_resolve:
        resolved_repositories: list[RepositorySettings] = []
        for repository in watcher.repositories:
            path = repository.path
            if path is not None and not path.is_absolute():
                path = config_path.parent / path
            if path is not None:
                path = path.resolve()
            resolved = repository.model_copy(update={"path": path})
            workspace_path = resolved.workspace_path(workspace_dir).resolve()
            previous_repo = workspace_paths.setdefault(workspace_path, resolved.repo)
            if previous_repo != resolved.repo:
                raise ValueError("different repositories cannot share a workspace path")
            resolved_repositories.append(resolved)
        resolved_watchers.append(watcher.model_copy(update={"repositories": resolved_repositories}))

    cron = settings.watchers.cron
    if cron is not None:
        resolved_jobs = []
        for job in cron.jobs:
            path = job.path
            if path is not None and not path.is_absolute():
                path = config_path.parent / path
            if path is not None:
                path = path.resolve()
            resolved = job.model_copy(update={"path": path})
            workspace_path = resolved.workspace_path(workspace_dir).resolve()
            previous_repo = workspace_paths.setdefault(workspace_path, resolved.repo)
            if previous_repo != resolved.repo:
                raise ValueError("different repositories cannot share a workspace path")
            resolved_jobs.append(resolved)
        cron = cron.model_copy(update={"jobs": resolved_jobs})

    watchers = settings.watchers.model_copy(
        update={
            "issues": resolved_watchers[0],
            "pull_requests": (
                resolved_watchers[1] if settings.watchers.pull_requests is not None else None
            ),
            "cron": cron,
        }
    )
    core = settings.core.model_copy(update={"workspace_dir": workspace_dir})
    state_db_path = settings.core.state_db_path
    if not state_db_path.is_absolute():
        state_db_path = config_path.parent / state_db_path
    state_db_path = state_db_path.resolve()
    core = core.model_copy(update={"state_db_path": state_db_path})
    return settings.model_copy(update={"watchers": watchers, "core": core})


async def load_settings(config_path: Path) -> AppSettings:
    """Load and validate configuration without blocking the event loop."""
    return await asyncio.to_thread(_load_settings_sync, config_path)


__all__ = ["AppSettings", "ValidationError", "load_settings"]
