"""Unit tests for assistant interactive launch planning."""

from pathlib import Path
from typing import ClassVar, Literal

import pytest
from typing_extensions import override

from curupira.agents.base import CodingAgentCliAdapter
from curupira.agents.interactive import InteractiveLaunchSpec
from curupira.config import ApplicationSettings
from curupira.models import CliProfileBase, CodingTaskRequest
from curupira.tui.assistant_launch import list_assistant_providers, plan_assistant_launch
from tests.helpers import settings_dict


class _PlanProfile(CliProfileBase):
    provider: Literal["plan-fake"] = "plan-fake"


class _PlanAdapter(CodingAgentCliAdapter):
    executable = "curupira-plan-fake-bin"
    provider = "plan-fake"
    profile_model = _PlanProfile
    display_name = "Plan Fake"
    install_url = "https://example.invalid/plan"
    auto_model: ClassVar[str | None] = None

    @override
    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        del request
        return ("--", "unused")

    @override
    def interactive_launch(
        self,
        profile: CliProfileBase,
        *,
        model: str | None,
        prompt: str | None,
        cwd: Path,
    ) -> InteractiveLaunchSpec:
        del profile, prompt
        self.ensure_interactive_model_resolved(model)
        argv = [self.executable]
        if model is not None:
            argv.extend(("--model", model))
        return InteractiveLaunchSpec(argv=tuple(argv), cwd=cwd)


def test_list_assistant_providers_includes_built_ins() -> None:
    providers = dict(list_assistant_providers())
    assert "cursor" in providers
    assert providers["cursor"] == "Cursor"


def test_plan_returns_none_when_agent_unset(tmp_path: Path) -> None:
    settings = ApplicationSettings.model_validate(
        settings_dict(
            {
                "daily": {
                    "trigger_type": "cron",
                    "repository": "api",
                    "schedule": "0 9 * * *",
                    "prompt": "Maintain ${repository}",
                }
            }
        )
    )
    assert plan_assistant_launch(settings, cwd=tmp_path) is None


def test_plan_reports_missing_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import curupira.agents.registry as agent_registry

    agent_registry.registered()
    monkeypatch.setattr(
        agent_registry,
        "_ADAPTERS",
        {**agent_registry._ADAPTERS, "plan-fake": _PlanAdapter},
    )

    def _create(provider: str, runner: object = None) -> CodingAgentCliAdapter:
        del runner
        return agent_registry.get(provider)()

    monkeypatch.setattr("curupira.tui.assistant_launch.create_cli_adapter", _create)
    settings = ApplicationSettings.model_validate(
        settings_dict(
            {
                "daily": {
                    "trigger_type": "cron",
                    "repository": "api",
                    "schedule": "0 9 * * *",
                    "prompt": "Maintain ${repository}",
                }
            },
            assistant={"agent": "plan-fake"},
        )
    )
    plan = plan_assistant_launch(settings, cwd=tmp_path)
    assert plan is not None
    assert plan.spec is None
    assert plan.notice is not None
    assert "no native automatic model" in plan.notice
    assert plan.error is not None
    assert "was not found on PATH" in plan.error


class _UnverifiedProfile(CliProfileBase):
    provider: Literal["plan-unverified"] = "plan-unverified"


class _UnverifiedAdapter(CodingAgentCliAdapter):
    """Default ``interactive_launch`` returns ``None`` (unverified)."""

    executable = "python"
    provider = "plan-unverified"
    profile_model = _UnverifiedProfile
    display_name = "Unverified Fake"
    install_url = "https://example.invalid/unverified"
    auto_model: ClassVar[str | None] = "auto"

    @override
    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        del request
        return ("--", "unused")


def test_plan_reports_unverified_interactive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import curupira.agents.registry as agent_registry

    agent_registry.registered()
    monkeypatch.setattr(
        agent_registry,
        "_ADAPTERS",
        {**agent_registry._ADAPTERS, "plan-unverified": _UnverifiedAdapter},
    )

    def _create(provider: str, runner: object = None) -> CodingAgentCliAdapter:
        del runner
        return agent_registry.get(provider)()

    monkeypatch.setattr("curupira.tui.assistant_launch.create_cli_adapter", _create)
    settings = ApplicationSettings.model_validate(
        settings_dict(
            {
                "daily": {
                    "trigger_type": "cron",
                    "repository": "api",
                    "schedule": "0 9 * * *",
                    "prompt": "Maintain ${repository}",
                }
            },
            assistant={"agent": "plan-unverified"},
        )
    )
    plan = plan_assistant_launch(settings, cwd=tmp_path)
    assert plan is not None
    assert plan.spec is None
    assert plan.error is not None
    assert "no verified interactive launch" in plan.error
