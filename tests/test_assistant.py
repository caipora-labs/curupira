"""Configuration assistant settings and model-resolution contracts."""

from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import ValidationError
from typing_extensions import override

from curupira.agents.assistant import ResolvedModel, resolve_assistant_model
from curupira.agents.base import CodingAgentCliAdapter
from curupira.config import ApplicationSettings, load_settings
from curupira.models import CodingTaskRequest
from curupira.models.profiles import OpenCodeCliProfile
from curupira.providers.cursor import CursorCliAdapter
from curupira.providers.opencode import OpenCodeCliAdapter
from tests.helpers import settings_dict


class _AutoAdapter(CodingAgentCliAdapter):
    """Fake adapter with a documented native auto model."""

    executable = "auto-agent"
    provider = "auto-provider"
    profile_model = OpenCodeCliProfile
    display_name = "Auto Provider"
    install_url = "https://example.test/auto"
    auto_model: ClassVar[str | None] = "auto"

    @override
    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        return (request.message,)


class _NoAutoAdapter(CodingAgentCliAdapter):
    """Fake adapter without native automatic model selection."""

    executable = "plain-agent"
    provider = "plain-provider"
    profile_model = OpenCodeCliProfile
    display_name = "Plain Provider"
    install_url = "https://example.test/plain"

    @override
    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        return (request.message,)


def test_assistant_settings_default_to_unset() -> None:
    settings = ApplicationSettings.model_validate(
        settings_dict(
            {
                "daily": {
                    "trigger_type": "github-issues",
                    "repo": "acme/api",
                    "prompt": "Handle ${task_title}",
                }
            }
        )
    )

    assert settings.assistant.agent is None
    assert settings.assistant.model is None


async def test_toml_without_assistant_table_keeps_defaults(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    config.write_text(
        """
[repositories.api]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "opencode"

[agents.profiles.opencode]
provider = "opencode"

[automations.daily]
trigger_type = "github-issues"
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
prompt = "Handle ${task_title}"
""",
        encoding="utf-8",
    )

    settings = await load_settings(config)

    assert settings.assistant.agent is None
    assert settings.assistant.model is None


async def test_toml_with_assistant_table_loads_agent_and_model(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    config.write_text(
        """
[repositories.api]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "cursor"

[agents.profiles.cursor]
provider = "cursor"

[assistant]
agent = "cursor"
model = "auto"

[automations.daily]
trigger_type = "github-issues"
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
prompt = "Handle ${task_title}"
""",
        encoding="utf-8",
    )

    settings = await load_settings(config)

    assert settings.assistant.agent == "cursor"
    assert settings.assistant.model == "auto"


def test_assistant_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError, match="extra"):
        ApplicationSettings.model_validate(
            settings_dict(
                {
                    "daily": {
                        "trigger_type": "github-issues",
                        "repo": "acme/api",
                        "prompt": "Handle ${task_title}",
                    }
                },
                assistant={"agent": "cursor", "mystery": True},
            )
        )


def test_assistant_rejects_unregistered_agent() -> None:
    with pytest.raises(ValidationError, match=r"assistant\.agent 'not-a-provider'"):
        ApplicationSettings.model_validate(
            settings_dict(
                {
                    "daily": {
                        "trigger_type": "github-issues",
                        "repo": "acme/api",
                        "prompt": "Handle ${task_title}",
                    }
                },
                assistant={"agent": "not-a-provider"},
            )
        )


def test_resolve_unset_requested_uses_native_auto() -> None:
    assert resolve_assistant_model(_AutoAdapter, None) == ResolvedModel(model="auto", notice=None)


def test_resolve_unset_requested_without_native_auto_omits_model() -> None:
    resolved = resolve_assistant_model(_NoAutoAdapter, None)

    assert resolved.model is None
    assert resolved.notice is not None
    assert "plain-provider" in resolved.notice
    assert "no native automatic model" in resolved.notice


def test_resolve_literal_auto_without_native_auto_raises() -> None:
    with pytest.raises(ValueError, match="no native automatic model"):
        resolve_assistant_model(_NoAutoAdapter, "auto")


def test_resolve_passes_other_requested_models_through() -> None:
    assert resolve_assistant_model(_AutoAdapter, "composer-2.5") == ResolvedModel(
        model="composer-2.5", notice=None
    )
    assert resolve_assistant_model(_NoAutoAdapter, "gpt-5") == ResolvedModel(
        model="gpt-5", notice=None
    )
    assert resolve_assistant_model(_AutoAdapter, "auto") == ResolvedModel(model="auto", notice=None)


def test_settings_reject_auto_for_adapter_without_native_auto() -> None:
    with pytest.raises(ValidationError, match="no native automatic model"):
        ApplicationSettings.model_validate(
            settings_dict(
                {
                    "daily": {
                        "trigger_type": "github-issues",
                        "repo": "acme/api",
                        "prompt": "Handle ${task_title}",
                    }
                },
                assistant={"agent": "opencode", "model": "auto"},
            )
        )


def test_settings_accept_auto_for_cursor() -> None:
    settings = ApplicationSettings.model_validate(
        settings_dict(
            {
                "daily": {
                    "trigger_type": "github-issues",
                    "repo": "acme/api",
                    "prompt": "Handle ${task_title}",
                }
            },
            assistant={"agent": "cursor", "model": "auto"},
        )
    )

    assert settings.assistant.agent == "cursor"
    assert settings.assistant.model == "auto"
    assert CursorCliAdapter.auto_model == "auto"
    assert OpenCodeCliAdapter.auto_model is None
