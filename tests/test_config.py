"""Configuration validation and side-effect-free resolution contracts."""

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from curupira.config import ApplicationSettings, load_settings
from curupira.models import (
    AgentDefaults,
    AgentsSettings,
    AzurePullRequestAutomationConfiguration,
    CodexCliProfile,
    CronAutomationConfiguration,
    CursorCliProfile,
    IssueAutomationConfiguration,
    PullRequestAutomationConfiguration,
    TrelloAutomationConfiguration,
)
from curupira.providers.copilot import CopilotCliProfile
from curupira.providers.gemini import GeminiCliProfile
from curupira.providers.kilo import KiloCliProfile
from curupira.providers.pi import PiCliProfile
from curupira.providers.qwen import QwenCodeCliProfile
from tests.helpers import settings_dict


def configuration(trigger: str = "github-issues", **overrides: Any) -> ApplicationSettings:
    """Build one independently named automation for boundary tests."""
    automation: dict[str, object] = {
        "trigger_type": trigger,
        "prompt": "Handle ${task_title}",
    }
    if trigger == "cron":
        automation["schedule"] = "0 9 * * 1"
    elif trigger == "trello-cli-cards":
        automation["board_id"] = "board123"
    elif trigger == "azure-cli-pull-requests":
        automation["repo"] = "contoso/api-project/api"
        automation["repository"] = "azure-api"
    else:
        automation["repo"] = "acme/api"
        automation["labels"] = ["agent-ready"]
    automation.update(overrides)
    return ApplicationSettings.model_validate(settings_dict({"daily": automation}))


@pytest.mark.parametrize(
    ("trigger", "expected"),
    [
        ("github-issues", IssueAutomationConfiguration),
        ("github-pull-requests", PullRequestAutomationConfiguration),
        ("azure-cli-pull-requests", AzurePullRequestAutomationConfiguration),
        ("trello-cli-cards", TrelloAutomationConfiguration),
        ("cron", CronAutomationConfiguration),
    ],
)
def test_discriminator_supports_independent_source_types(trigger: str, expected: type) -> None:
    settings = configuration(trigger)
    assert isinstance(settings.automations["daily"], expected)
    assert settings.settings.max_active_tasks == 1
    assert settings.resolve_automations()["daily"].profile.provider == "opencode"
    assert settings.automations["daily"].checkout == "worktree"


def test_task_timeout_minutes_defaults_to_twenty() -> None:
    settings = configuration()
    assert settings.settings.task_timeout_minutes == 20
    assert settings.settings.task_timeout_seconds == 1200.0


def test_task_timeout_minutes_converts_to_seconds() -> None:
    settings = ApplicationSettings.model_validate(
        settings_dict(
            {
                "daily": {
                    "trigger_type": "github-issues",
                    "repo": "acme/api",
                    "labels": ["agent-ready"],
                    "prompt": "Handle ${task_title}",
                }
            },
            settings={"task_timeout_minutes": 5},
        )
    )
    assert settings.settings.task_timeout_minutes == 5
    assert settings.settings.task_timeout_seconds == 300.0


@pytest.mark.parametrize("value", [0, -1])
def test_task_timeout_minutes_must_be_positive(value: int) -> None:
    with pytest.raises(ValidationError, match="task_timeout_minutes"):
        ApplicationSettings.model_validate(
            settings_dict(
                {
                    "daily": {
                        "trigger_type": "github-issues",
                        "repo": "acme/api",
                        "prompt": "Handle ${task_title}",
                    }
                },
                settings={"task_timeout_minutes": value},
            )
        )


def test_legacy_task_timeout_seconds_is_rejected() -> None:
    with pytest.raises(ValidationError, match="task_timeout_seconds"):
        ApplicationSettings.model_validate(
            settings_dict(
                {
                    "daily": {
                        "trigger_type": "github-issues",
                        "repo": "acme/api",
                        "prompt": "Handle ${task_title}",
                    }
                },
                settings={"task_timeout_seconds": 3600},
            )
        )


@pytest.mark.parametrize(
    "setup_script", ["", "/absolute/setup", "../setup", r"C:\\setup", "nested/../setup"]
)
def test_invalid_setup_script_path_is_rejected(setup_script: str) -> None:
    with pytest.raises(ValidationError, match="setup_script"):
        ApplicationSettings.model_validate(
            settings_dict(
                {
                    "daily": {
                        "trigger_type": "github-issues",
                        "repo": "acme/api",
                        "prompt": "Handle ${task_title}",
                    }
                },
                repositories={
                    "api": {
                        "remote": "https://github.com/acme/api.git",
                        "setup_script": setup_script,
                    }
                },
            )
        )


def test_checkout_options_and_repository_setup_script_are_validated() -> None:
    settings = ApplicationSettings.model_validate(
        settings_dict(
            {
                "daily": {
                    "trigger_type": "github-issues",
                    "repo": "acme/api",
                    "checkout": "main",
                    "prompt": "Handle ${task_title}",
                }
            },
            repositories={
                "api": {
                    "remote": "https://github.com/acme/api.git",
                    "setup_script": "scripts/setup.sh",
                }
            },
        )
    )
    assert settings.automations["daily"].checkout == "main"
    assert settings.resolve_automations()["daily"].setup_script == "scripts/setup.sh"
    with pytest.raises(ValidationError, match="checkout"):
        configuration(checkout="develop")


def test_pull_request_automation_accepts_mergeable_filter() -> None:
    settings = configuration("github-pull-requests", mergeable=True, draft=False)

    automation = settings.automations["daily"]
    assert isinstance(automation, PullRequestAutomationConfiguration)
    assert automation.mergeable is True
    assert automation.draft is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"id": "duplicate"},
        {"poll_interval_seconds": 1},
        {"unexpected": True},
        {"repo": "../api"},
        {"repo": "invalid"},
        {"prompt": " "},
        {"prompt": "${unknown}"},
        {"prompt": "$"},
        {"prompt": "${pull_request_number}"},
        {"profile": "absent"},
        {"repository": "missing"},
    ],
)
def test_invalid_automation_is_rejected(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        configuration(**overrides)


def test_unregistered_trigger_type_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown trigger type: unknown"):
        configuration("unknown")


def test_short_pull_request_alias_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unknown trigger type: pull_request"):
        configuration("pull_request")


def test_registered_alias_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    import curupira.tasks  # noqa: F401
    from curupira.tasks import registry

    monkeypatch.setattr(registry, "_ALIASES", {})
    registry.register_alias("github-issues", "legacy_issue")

    automation = configuration("legacy_issue").automations["daily"]

    assert automation.trigger_type == "legacy_issue"


@pytest.mark.parametrize("field", ["max_active_tasks", "max_pending_tasks"])
@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_execution_counts_require_positive_integers(field: str, value: object) -> None:
    data = configuration().model_dump()
    data["settings"][field] = value
    with pytest.raises(ValidationError):
        ApplicationSettings.model_validate(data)


@pytest.mark.parametrize("value", [0, -1, float("inf"), float("nan")])
def test_poll_interval_requires_finite_positive_value(value: float) -> None:
    data = configuration().model_dump()
    data["settings"]["polling"]["poll_interval_seconds"] = value
    with pytest.raises(ValidationError):
        ApplicationSettings.model_validate(data)


def test_codex_agent_selects_a_named_cli_profile() -> None:
    data = configuration().model_dump()
    data["agents"]["profiles"]["opencode"] = {
        "provider": "codex",
        "agent": "work",
    }

    profile = ApplicationSettings.model_validate(data).resolve_automations()["daily"].profile

    assert isinstance(profile, CodexCliProfile)
    assert profile.agent == "work"


def test_kilo_provider_selects_its_registered_profile() -> None:
    data = configuration().model_dump()
    data["agents"]["profiles"]["opencode"] = {
        "provider": "kilo",
        "model": "anthropic/claude-sonnet-4",
        "effort": "high",
    }

    profile = ApplicationSettings.model_validate(data).resolve_automations()["daily"].profile

    assert isinstance(profile, KiloCliProfile)
    assert profile.provider == "kilo"
    assert profile.model == "anthropic/claude-sonnet-4"


def test_kilo_rejects_model_without_provider_prefix() -> None:
    data = configuration().model_dump()
    data["agents"]["profiles"]["opencode"] = {
        "provider": "kilo",
        "model": "claude-sonnet-4",
    }

    with pytest.raises(ValidationError, match="provider/model"):
        ApplicationSettings.model_validate(data)


@pytest.mark.parametrize("mode", ["agent", "ask", "plan"])
def test_cursor_agent_selects_a_native_mode(mode: str) -> None:
    data = configuration().model_dump()
    data["agents"]["profiles"]["opencode"] = {"provider": "cursor", "agent": mode}

    profile = ApplicationSettings.model_validate(data).resolve_automations()["daily"].profile

    assert isinstance(profile, CursorCliProfile)
    assert profile.agent == mode


def test_cursor_rejects_unknown_agent_modes() -> None:
    data = configuration().model_dump()
    data["agents"]["profiles"]["opencode"] = {
        "provider": "cursor",
        "agent": "reviewer",
    }

    with pytest.raises(ValidationError, match="agent"):
        ApplicationSettings.model_validate(data)


def test_gemini_provider_selects_a_gemini_cli_profile() -> None:
    data = configuration().model_dump()
    data["agents"]["profiles"]["opencode"] = {"provider": "gemini"}

    profile = ApplicationSettings.model_validate(data).resolve_automations()["daily"].profile

    assert isinstance(profile, GeminiCliProfile)
    assert profile.provider == "gemini"


def test_copilot_provider_validates_as_a_registered_profile() -> None:
    data = configuration().model_dump()
    data["agents"]["profiles"]["opencode"] = {
        "provider": "copilot",
        "allow_tools": ["shell(git:*)"],
    }

    profile = ApplicationSettings.model_validate(data).resolve_automations()["daily"].profile

    assert isinstance(profile, CopilotCliProfile)
    assert profile.provider == "copilot"


def test_trello_provider_is_rejected() -> None:
    data = configuration().model_dump()
    data["agents"]["profiles"]["opencode"] = {"provider": "trello"}

    with pytest.raises(ValidationError, match="unknown coding agent provider: trello"):
        ApplicationSettings.model_validate(data)


def test_cursor_rejects_effort_and_codex_accepts_optional_effort() -> None:
    data = configuration().model_dump()
    data["agents"]["profiles"]["opencode"] = {"provider": "cursor", "effort": "high"}
    with pytest.raises(ValidationError, match="effort"):
        ApplicationSettings.model_validate(data)
    data["agents"]["profiles"]["opencode"] = {"provider": "codex", "effort": "high"}
    assert (
        ApplicationSettings.model_validate(data).resolve_automations()["daily"].profile.provider
        == "codex"
    )


def test_qwen_provider_selects_qwen_code_profile() -> None:
    data = configuration().model_dump()
    data["agents"]["profiles"]["opencode"] = {
        "provider": "qwen",
        "model": "qwen3-coder-plus",
        "approval_mode": "auto-edit",
        "max_session_turns": 12,
    }

    profile = ApplicationSettings.model_validate(data).resolve_automations()["daily"].profile

    assert isinstance(profile, QwenCodeCliProfile)
    assert profile.provider == "qwen"
    assert profile.approval_mode == "auto-edit"
    assert profile.max_session_turns == 12


def test_pi_provider_selects_pi_profile() -> None:
    data = configuration().model_dump()
    data["agents"]["profiles"]["opencode"] = {
        "provider": "pi",
        "model": "anthropic/claude-sonnet-4",
        "model_provider": "anthropic",
    }

    profile = ApplicationSettings.model_validate(data).resolve_automations()["daily"].profile

    assert isinstance(profile, PiCliProfile)
    assert profile.provider == "pi"
    assert profile.model_provider == "anthropic"


def test_cron_defaults_normalize_dates_before_comparing_windows() -> None:
    data = configuration("cron", start_date="2026-10-05T09:00:00").model_dump()
    data["agents"]["defaults"]["timezone"] = "Europe/Rome"
    resolved = ApplicationSettings.model_validate(data).resolve_automations()["daily"]
    assert isinstance(resolved.configuration, CronAutomationConfiguration)
    start = resolved.configuration.start_date
    assert start is not None
    offset = start.utcoffset()
    assert offset is not None
    assert offset.total_seconds() == 7200
    assert resolved.timezone == "Europe/Rome"


@pytest.mark.parametrize(
    "overrides",
    [
        {"schedule": "invalid"},
        {"schedule": "* * * * * *"},
        {"timezone": "Missing/Timezone"},
        {"start_date": "2026-12-01", "end_date": "2026-01-01"},
    ],
)
def test_invalid_cron_schedule_is_rejected(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        configuration("cron", **overrides)


def test_automation_keys_and_profile_references_are_validated() -> None:
    data = configuration().model_dump()
    data["automations"]["bad key"] = data["automations"]["daily"]
    with pytest.raises(ValidationError):
        ApplicationSettings.model_validate(data)
    data = configuration().model_dump()
    data["agents"]["defaults"]["profile"] = "absent"
    with pytest.raises(ValidationError, match="default profile"):
        ApplicationSettings.model_validate(data)


async def test_relative_paths_resolve_without_creating_workspaces(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        '[settings]\nworkspace_dir="workspaces"\nstate_db_path="state/db.sqlite3"\n'
        '[repositories.api]\nremote="https://github.com/acme/api.git"\npath="checkout"\n'
        '[agents.defaults]\nprofile="opencode"\n'
        '[agents.profiles.opencode]\nprovider="opencode"\n'
        '[automations.daily]\ntrigger_type="cron"\nrepository="api"\n'
        'schedule="0 9 * * *"\nprompt="Maintain ${repository}"\n',
        encoding="utf-8",
    )
    settings = await load_settings(config)
    assert settings.settings.workspace_dir == tmp_path / "workspaces"
    assert settings.settings.state_db_path == tmp_path / "state/db.sqlite3"
    assert settings.resolve_automations()["daily"].workspace_path == tmp_path / "checkout"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["config.toml"]


async def test_otlp_endpoint_is_optional_and_loaded_from_toml(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    config.write_text(
        '[settings]\notlp_endpoint="http://collector:4318/v1/traces"\n'
        '[repositories.api]\nremote="https://github.com/acme/api.git"\n'
        '[agents.defaults]\nprofile="opencode"\n'
        '[agents.profiles.opencode]\nprovider="opencode"\n'
        '[automations.daily]\ntrigger_type="cron"\nrepository="api"\n'
        'schedule="0 9 * * *"\nprompt="Maintain ${repository}"\n',
        encoding="utf-8",
    )

    settings = await load_settings(config)

    assert str(settings.settings.otlp_endpoint) == "http://collector:4318/v1/traces"
    assert configuration().settings.otlp_endpoint is None


def test_otlp_endpoint_rejects_non_http_urls() -> None:
    data = configuration().model_dump()
    data["settings"]["otlp_endpoint"] = "grpc://collector:4317"

    with pytest.raises(ValidationError, match="URL"):
        ApplicationSettings.model_validate(data)


def test_shared_workspaces_require_the_same_repository_alias(tmp_path: Path) -> None:
    data = settings_dict(
        {
            "daily": {
                "trigger_type": "github-issues",
                "repository": "api",
                "repo": "acme/api",
                "prompt": "Handle ${task_title}",
            },
            "other": {
                "trigger_type": "github-issues",
                "repository": "other",
                "repo": "acme/other",
                "prompt": "Handle ${task_title}",
            },
        },
        repositories={
            "api": {"remote": "https://github.com/acme/api.git", "path": str(tmp_path)},
            "other": {"remote": "https://github.com/acme/other.git", "path": str(tmp_path)},
        },
    )
    with pytest.raises(ValidationError, match="share a workspace"):
        ApplicationSettings.model_validate(data)
    data["automations"]["other"]["repository"] = "api"
    del data["repositories"]["other"]
    assert len(ApplicationSettings.model_validate(data).automations) == 2


async def test_missing_file_and_environment_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(FileNotFoundError, match="configuration file not found"):
        await load_settings(tmp_path / "absent.toml")
    monkeypatch.setenv("SETTINGS", '{"max_active_tasks": 999}')
    assert configuration().settings.max_active_tasks == 1


def test_json_schema_describes_the_shared_automation_contract() -> None:
    schema = ApplicationSettings.model_json_schema()
    automations = schema["properties"]["automations"]
    values = next(iter(automations["patternProperties"].values()))
    assert values["$ref"].endswith("/AutomationConfigurationBase")
    base = schema["$defs"]["AutomationConfigurationBase"]
    assert {"trigger_type", "repository", "prompt"} <= set(base["required"])
    assert "RepositoryConfiguration" in schema["$defs"]


@pytest.mark.parametrize("model", [ApplicationSettings, AgentsSettings, AgentDefaults])
def test_root_config_models_expose_non_empty_field_descriptions(
    model: type[ApplicationSettings] | type[AgentsSettings] | type[AgentDefaults],
) -> None:
    """Every field on the root TOML models carries a schema description."""
    schema = model.model_json_schema()
    assert schema.get("description", "").strip()
    assert "Attributes:" not in (model.__doc__ or "")
    properties = schema.get("properties")
    assert properties
    for name, prop in properties.items():
        assert prop.get("description", "").strip(), name


def test_azure_pull_request_automation_accepts_status_and_branch_filters() -> None:
    settings = configuration(
        "azure-cli-pull-requests",
        status="all",
        source_branch="feature",
        target_branch="main",
    )

    automation = settings.automations["daily"]
    assert isinstance(automation, AzurePullRequestAutomationConfiguration)
    assert automation.status == "all"
    assert automation.source_branch == "feature"
    assert automation.target_branch == "main"


@pytest.mark.parametrize("repo", ["acme/api", "contoso/api-project", "a/b/c/d"])
def test_azure_pull_request_rejects_non_three_part_repos(repo: str) -> None:
    with pytest.raises(ValidationError, match="organization/project/repository"):
        configuration("azure-cli-pull-requests", repo=repo)


async def test_example_configuration_is_valid() -> None:
    settings = await load_settings(Path("curupira.example.toml"))
    assert "resolve-ready-issues" in settings.automations
    assert settings.repositories["api"].remote.endswith("acme/api.git")
