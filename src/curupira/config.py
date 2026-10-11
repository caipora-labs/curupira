"""TOML-authoritative Pydantic Settings and validated default resolution."""

import asyncio
from pathlib import Path
from string import Template
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)
from typing_extensions import override

from curupira.models import (
    AgentsSettings,
    AssistantSettings,
    CronAutomationConfiguration,
    ExecutionSettings,
    ResolvedAutomation,
)
from curupira.models.base import Identifier
from curupira.models.configuration import (
    COMMON_PROMPT_FIELDS,
    AutomationConfiguration,
    RepositoryConfiguration,
    forge_identity,
    normalize_date,
)


class ApplicationSettings(BaseSettings):
    """Application configuration; environment variables do not override the TOML."""

    model_config = SettingsConfigDict(extra="forbid", validate_default=True)
    settings: ExecutionSettings = Field(default_factory=ExecutionSettings)
    repositories: dict[Identifier, RepositoryConfiguration] = Field(min_length=1)
    agents: AgentsSettings
    automations: dict[Identifier, AutomationConfiguration] = Field(min_length=1)
    assistant: AssistantSettings = Field(
        default_factory=AssistantSettings,
        description=(
            "Interactive configuration assistant preferences. When the TOML omits "
            "``[assistant]``, both agent and model stay unset."
        ),
    )

    @model_validator(mode="after")
    def validate_cross_references(self) -> "ApplicationSettings":
        """Validate automation references, prompts, cron windows, and workspace ownership."""
        from curupira.agents.assistant import resolve_assistant_model
        from curupira.agents.registry import registered
        from curupira.tasks.registry import get

        defaults = self.agents.defaults
        paths: dict[Path, str] = {}
        for name, automation in self.automations.items():
            repository = self.repositories.get(automation.repository)
            if repository is None:
                raise ValueError(
                    f"repository {automation.repository!r} for automation {name!r} does not exist"
                )
            profile = automation.profile or defaults.profile
            if profile not in self.agents.profiles:
                raise ValueError(f"profile {profile!r} for automation {name!r} does not exist")
            allowed = COMMON_PROMPT_FIELDS | get(automation.trigger_type).prompt_fields()
            unknown = set(Template(automation.prompt).get_identifiers()) - allowed
            if unknown:
                raise ValueError(f"unsupported prompt placeholders for {name!r}: {sorted(unknown)}")
            if isinstance(automation, CronAutomationConfiguration):
                timezone = ZoneInfo(automation.timezone or defaults.timezone)
                start = normalize_date(automation.start_date, timezone)
                end = normalize_date(automation.end_date, timezone)
                if start is not None and end is not None and end < start:
                    raise ValueError(
                        f"end_date must be greater than or equal to start_date: {name}"
                    )
            workspace = (
                repository.path or self.settings.workspace_dir / automation.repository
            ).resolve()
            previous = paths.setdefault(workspace, automation.repository)
            if previous != automation.repository:
                raise ValueError("different repositories cannot share a workspace path")
        if self.assistant.agent is not None:
            adapters = registered()
            adapter = adapters.get(self.assistant.agent)
            if adapter is None:
                available = ", ".join(sorted(adapters))
                raise ValueError(
                    f"assistant.agent {self.assistant.agent!r} is not a registered coding "
                    f"agent provider; registered providers: {available}"
                )
            resolve_assistant_model(adapter, self.assistant.model)
        return self

    def resolve_automations(self) -> dict[str, ResolvedAutomation]:
        """Create validated execution snapshots, preserving configuration order."""
        resolved: dict[str, ResolvedAutomation] = {}
        defaults = self.agents.defaults
        for name, configured in self.automations.items():
            configuration = configured
            timezone: str | None = None
            if isinstance(configured, CronAutomationConfiguration):
                timezone = configured.timezone or defaults.timezone
                data = configured.model_dump()
                data.update(
                    timezone=timezone,
                    start_date=normalize_date(configured.start_date, ZoneInfo(timezone)),
                    end_date=normalize_date(configured.end_date, ZoneInfo(timezone)),
                )
                configuration = CronAutomationConfiguration.model_validate(data)
            repository = self.repositories[configuration.repository]
            path = repository.path or self.settings.workspace_dir / configuration.repository
            resolved[name] = ResolvedAutomation(
                automation_id=name,
                configuration=configuration,
                profile=self.agents.profiles[configuration.profile or defaults.profile],
                workspace_path=path.resolve(),
                repository_id=configuration.repository,
                remote=repository.remote,
                setup_script=repository.setup_script,
                identity_repo=forge_identity(configuration, configuration.repository),
                timezone=timezone,
            )
        return resolved

    @classmethod
    @override
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        toml_file = settings_cls.model_config.get("toml_file")
        if toml_file is None:
            return (init_settings,)
        return (init_settings, TomlConfigSettingsSource(settings_cls, toml_file=toml_file))


def _load_settings_sync(config_path: Path) -> ApplicationSettings:
    config_path = config_path.expanduser().resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"configuration file not found: {config_path}")

    class FileSettings(ApplicationSettings):
        model_config = SettingsConfigDict(
            toml_file=config_path, extra="forbid", validate_default=True
        )

    declared = FileSettings()
    data = declared.model_dump()
    execution = data["settings"]
    for field in ("workspace_dir", "state_db_path"):
        value = getattr(declared.settings, field)
        execution[field] = (config_path.parent / value).resolve()
    for name, repository in declared.repositories.items():
        if repository.path is not None:
            data["repositories"][name]["path"] = (config_path.parent / repository.path).resolve()
    return ApplicationSettings.model_validate(data)


async def load_settings(config_path: Path) -> ApplicationSettings:
    """Load and resolve a configuration without blocking the event loop or writing files."""
    return await asyncio.to_thread(_load_settings_sync, config_path)
