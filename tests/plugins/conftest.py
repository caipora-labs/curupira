"""Isolate plugin registries and entry-point discovery for each test."""

import pytest

import curupira.agents.registry as agent_registry
import curupira.plugins as plugins
import curupira.tasks.registry as registry
from tests.plugins.entry_points import FakeEntryPoint, Install


@pytest.fixture
def install(monkeypatch: pytest.MonkeyPatch) -> Install:
    registry.registered()
    agent_registry.registered()
    monkeypatch.setattr(registry, "_TRIGGERS", dict(registry._TRIGGERS))
    monkeypatch.setattr(registry, "_ALIASES", dict(registry._ALIASES))
    monkeypatch.setattr(agent_registry, "_ADAPTERS", dict(agent_registry._ADAPTERS))
    monkeypatch.setattr(plugins, "_loaded", None)
    monkeypatch.setattr(plugins, "_agents_loaded", None)

    def install_entry_points(*installed: FakeEntryPoint) -> None:
        def entry_points(group: str) -> list[FakeEntryPoint]:
            return [entry for entry in installed if entry.group == group]

        monkeypatch.setattr(plugins, "entry_points", entry_points)

    install_entry_points()
    return install_entry_points
