"""Pluggy manager loads built-in providers through the shared hook contract."""

import pluggy
import pytest

import curupira.agents.registry as agent_registry
import curupira.manager as manager_module
import curupira.tasks.registry as trigger_registry
from curupira.hooks import PROJECT_NAME, hookimpl
from curupira.manager import (
    collect_built_in_adapters,
    collect_built_in_triggers,
    create_manager,
    load_built_in_providers,
    register_built_in_providers,
)
from curupira.providers.cursor import CursorCliAdapter
from curupira.providers.cursor import provider as cursor_provider
from curupira.providers.github import IssueTrigger, PullRequestTrigger
from curupira.providers.github import provider as github_provider
from curupira.providers.opencode import OpenCodeCliAdapter
from curupira.tasks.base import Trigger


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    agent_registry.registered()
    trigger_registry.registered()
    monkeypatch.setattr(agent_registry, "_ADAPTERS", dict(agent_registry._ADAPTERS))
    monkeypatch.setattr(trigger_registry, "_TRIGGERS", dict(trigger_registry._TRIGGERS))
    monkeypatch.setattr(trigger_registry, "_ALIASES", dict(trigger_registry._ALIASES))
    monkeypatch.setattr(manager_module, "_loaded", True)


def test_create_manager_exposes_agent_and_trigger_hooks() -> None:
    plugin_manager = create_manager()

    assert isinstance(plugin_manager, pluggy.PluginManager)
    assert plugin_manager.project_name == PROJECT_NAME
    assert hasattr(plugin_manager.hook, "curupira_coding_agent_adapters")
    assert hasattr(plugin_manager.hook, "curupira_triggers")


def test_collect_built_in_adapters_includes_official_providers() -> None:
    plugin_manager = create_manager()
    register_built_in_providers(plugin_manager)

    adapters = collect_built_in_adapters(plugin_manager)
    providers = {adapter.provider: adapter for adapter in adapters}

    assert providers["cursor"] is CursorCliAdapter
    assert providers["opencode"] is OpenCodeCliAdapter
    assert len(adapters) == len(agent_registry.registered())


def test_collect_built_in_triggers_includes_official_providers() -> None:
    plugin_manager = create_manager()
    register_built_in_providers(plugin_manager)

    triggers = collect_built_in_triggers(plugin_manager)
    by_type = {trigger.trigger_type: trigger for trigger in triggers}

    assert set(by_type) == {
        "issue",
        "github-cli-pull-requests",
        "azure-cli-pull-requests",
        "cron",
        "trello-cli-cards",
    }
    assert isinstance(by_type["issue"], IssueTrigger)
    assert isinstance(by_type["github-cli-pull-requests"], PullRequestTrigger)
    assert len(triggers) == len(trigger_registry.registered())


def test_load_built_in_providers_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(manager_module, "_loaded", False)
    monkeypatch.setattr(agent_registry, "_ADAPTERS", {})
    monkeypatch.setattr(trigger_registry, "_TRIGGERS", {})
    monkeypatch.setattr(trigger_registry, "_ALIASES", {})

    load_built_in_providers()
    first_agents = dict(agent_registry._ADAPTERS)
    first_triggers = dict(trigger_registry._TRIGGERS)
    load_built_in_providers()

    assert first_agents == agent_registry._ADAPTERS
    assert first_triggers == trigger_registry._TRIGGERS
    assert "cursor" in first_agents
    assert "issue" in first_triggers


def test_coding_agent_provider_modules_implement_the_pluggy_hook() -> None:
    assert hookimpl.project_name == PROJECT_NAME
    contributed = cursor_provider.curupira_coding_agent_adapters()
    assert contributed == (CursorCliAdapter,)


def test_github_provider_contributes_multiple_triggers() -> None:
    contributed = github_provider.curupira_triggers()
    assert len(contributed) == 2
    assert {trigger.trigger_type for trigger in contributed} == {
        "issue",
        "github-cli-pull-requests",
    }
    assert all(isinstance(trigger, Trigger) for trigger in contributed)


def test_provider_can_contribute_agents_and_triggers() -> None:
    """A single Pluggy provider module may implement both hooks."""

    class DualProvider:
        @hookimpl
        def curupira_coding_agent_adapters(self) -> tuple[type[CursorCliAdapter], ...]:
            return (CursorCliAdapter,)

        @hookimpl
        def curupira_triggers(self) -> tuple[Trigger, ...]:
            return (IssueTrigger(), PullRequestTrigger())

    plugin_manager = create_manager()
    plugin_manager.register(DualProvider())

    adapters = collect_built_in_adapters(plugin_manager)
    triggers = collect_built_in_triggers(plugin_manager)

    assert adapters == [CursorCliAdapter]
    assert {trigger.trigger_type for trigger in triggers} == {
        "issue",
        "github-cli-pull-requests",
    }
