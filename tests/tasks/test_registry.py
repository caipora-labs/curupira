"""Trigger registration and lookup contract tests."""

from __future__ import annotations

import pytest
from typing_extensions import override

import curupira.tasks.registry as registry
from curupira.models import ResolvedAutomation, Task
from curupira.models.base import ValidatedModel
from curupira.tasks.base import FeedDependencies, TaskFeed, Trigger
from curupira.tasks.registry import for_configuration, get, register


class FakeConfiguration(ValidatedModel):
    """Configuration shape used only by FakeTrigger registry tests."""


class FakeTrigger(Trigger):
    """Minimal implementation used to exercise the trigger registry."""

    trigger_type = "fake"
    configuration_type = FakeConfiguration

    @classmethod
    @override
    def prompt_fields(cls) -> frozenset[str]:
        return frozenset({"fake_value"})

    @override
    def prompt_context(self, task: Task) -> dict[str, str]:
        return {"fake_value": task.title}

    @override
    def build_feed(
        self, automation: ResolvedAutomation, dependencies: FeedDependencies
    ) -> TaskFeed:
        raise NotImplementedError


def test_register_and_get_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "_TRIGGERS", {})
    monkeypatch.setattr(registry, "_BY_CONFIGURATION", {})
    trigger = FakeTrigger()

    register(trigger)

    assert get("fake") is trigger
    assert for_configuration(FakeConfiguration()) is trigger


def test_register_duplicate_trigger_type_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "_TRIGGERS", {})
    monkeypatch.setattr(registry, "_BY_CONFIGURATION", {})
    register(FakeTrigger())

    with pytest.raises(ValueError, match="trigger type already registered: fake"):
        register(FakeTrigger())


def test_register_duplicate_configuration_type_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "_TRIGGERS", {})
    monkeypatch.setattr(registry, "_BY_CONFIGURATION", {})
    register(FakeTrigger())

    class OtherFakeTrigger(FakeTrigger):
        trigger_type = "other-fake"

    with pytest.raises(
        ValueError, match="configuration type already registered: FakeConfiguration"
    ):
        register(OtherFakeTrigger())


def test_get_unknown_trigger_type_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "_TRIGGERS", {})
    monkeypatch.setattr(registry, "_ALIASES", {})
    with pytest.raises(ValueError, match="unknown trigger type: missing"):
        get("missing")


def test_for_configuration_unknown_type_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "_BY_CONFIGURATION", {})
    with pytest.raises(
        ValueError, match="no trigger registered for configuration type: FakeConfiguration"
    ):
        for_configuration(FakeConfiguration())


def test_alias_resolves_to_registered_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "_TRIGGERS", {})
    monkeypatch.setattr(registry, "_ALIASES", {})
    monkeypatch.setattr(registry, "_BY_CONFIGURATION", {})
    trigger = FakeTrigger()
    register(trigger)

    registry.register_alias("fake", "legacy_fake")

    assert get("legacy_fake") is trigger


def test_duplicate_alias_and_canonical_collision_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "_TRIGGERS", {})
    monkeypatch.setattr(registry, "_ALIASES", {})
    monkeypatch.setattr(registry, "_BY_CONFIGURATION", {})
    register(FakeTrigger())
    registry.register_alias("fake", "legacy_fake")

    with pytest.raises(ValueError, match="trigger alias already registered: legacy_fake"):
        registry.register_alias("fake", "legacy_fake")
    with pytest.raises(ValueError, match="trigger alias already registered: fake"):
        registry.register_alias("fake", "fake")
