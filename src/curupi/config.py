"""TOML-authoritative Pydantic Settings and validated default resolution."""

import asyncio
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)
from typing_extensions import override

from curupi.models import (
    CodingAgentsSettings,
    CronAutomationConfiguration,
    ExecutionSettings,
    ResolvedAutomation,
)
from curupi.models.configuration import normalize_date


class ApplicationSettings(BaseSettings):
    """Application configuration; environment variables do not override the TOML."""

    model_config = SettingsConfigDict(extra="forbid", validate_default=True)
    settings: ExecutionSettings = Field(default_factory=ExecutionSettings)
    coding_agents: CodingAgentsSettings

    @model_validator(mode="after")
    def validate_workspace_ownership(self) -> "ApplicationSettings":
        """Reject workspace paths shared by different repositories."""
        paths: dict[Path, str] = {}
        for resolved in self.resolve_automations().values():
            previous = paths.setdefault(
                resolved.workspace_path.resolve(), resolved.configuration.repo
            )
            if previous != resolved.configuration.repo:
                raise ValueError("different repositories cannot share a workspace path")
        return self

    def resolve_automations(self) -> dict[str, ResolvedAutomation]:
        """Create validated execution snapshots, preserving configuration order."""
        resolved: dict[str, ResolvedAutomation] = {}
        defaults = self.coding_agents.defaults
        for name, configured in self.coding_agents.automations.items():
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
            path = configuration.path or self.settings.workspace_dir.joinpath(
                *configuration.repo.split("/")
            )
            resolved[name] = ResolvedAutomation(
                automation_id=name,
                configuration=configuration,
                profile=self.coding_agents.profiles[configuration.profile or defaults.profile],
                workspace_path=path.resolve(),
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
    for name, automation in declared.coding_agents.automations.items():
        if automation.path is not None:
            data["coding_agents"]["automations"][name]["path"] = (
                config_path.parent / automation.path
            ).resolve()
    return ApplicationSettings.model_validate(data)


async def load_settings(config_path: Path) -> ApplicationSettings:
    """Load and resolve a configuration without blocking the event loop or writing files."""
    return await asyncio.to_thread(_load_settings_sync, config_path)
