"""Pluggy manager loads built-in providers through the shared hook contract."""

import pluggy
import pytest

import curupira.agents.registry as agent_registry
import curupira.manager as manager_module
from curupira.hooks import PROJECT_NAME, hookimpl
from curupira.manager import (
    collect_built_in_adapters,
    create_manager,
    load_built_in_adapters,
    register_built_in_providers,
)
from curupira.providers.cursor import CursorCliAdapter
from curupira.providers.cursor import provider as cursor_provider
from curupira.providers.opencode import OpenCodeCliAdapter


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    agent_registry.registered()
    monkeypatch.setattr(agent_registry, "_ADAPTERS", dict(agent_registry._ADAPTERS))
    monkeypatch.setattr(manager_module, "_loaded", True)


def test_create_manager_exposes_coding_agent_hook() -> None:
    plugin_manager = create_manager()

    assert isinstance(plugin_manager, pluggy.PluginManager)
    assert plugin_manager.project_name == PROJECT_NAME
    assert hasattr(plugin_manager.hook, "curupira_coding_agent_adapters")


def test_collect_built_in_adapters_includes_official_providers() -> None:
    plugin_manager = create_manager()
    register_built_in_providers(plugin_manager)

    adapters = collect_built_in_adapters(plugin_manager)
    providers = {adapter.provider: adapter for adapter in adapters}

    assert providers["cursor"] is CursorCliAdapter
    assert providers["opencode"] is OpenCodeCliAdapter
    assert len(adapters) == len(agent_registry.registered())


def test_load_built_in_adapters_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(manager_module, "_loaded", False)
    monkeypatch.setattr(agent_registry, "_ADAPTERS", {})

    load_built_in_adapters()
    first = dict(agent_registry._ADAPTERS)
    load_built_in_adapters()

    assert first == agent_registry._ADAPTERS
    assert "cursor" in first


def test_built_in_provider_modules_implement_the_pluggy_hook() -> None:
    assert hookimpl.project_name == PROJECT_NAME
    contributed = cursor_provider.curupira_coding_agent_adapters()
    assert contributed == (CursorCliAdapter,)
