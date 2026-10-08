"""Trigger registration and lookup contract tests."""

from __future__ import annotations

from typing import cast

import pytest
from typing_extensions import override

import curupira.tasks.registry as registry
from curupira.models import ResolvedAutomation, Task
from curupira.models.configuration import AutomationConfigurationBase
from curupira.tasks.base import FeedDependencies, TaskFeed, Trigger
from curupira.tasks.registry import get, register


class FakeConfiguration(AutomationConfigurationBase):
    trigger_type: str = "fake"


class MismatchedConfiguration(AutomationConfigurationBase):
    trigger_type: str = "other"


class FakeTrigger(Trigger):
    """Minimal implementation used to exercise the trigger registry."""

    trigger_type = "fake"
    configuration_model = FakeConfiguration

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
    trigger = FakeTrigger()

    register(trigger)

    assert get("fake") is trigger


def test_register_duplicate_trigger_type_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "_TRIGGERS", {})
    register(FakeTrigger())

    with pytest.raises(ValueError, match="trigger type already registered: fake"):
        register(FakeTrigger())


def test_get_unknown_trigger_type_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "_TRIGGERS", {})
    monkeypatch.setattr(registry, "_ALIASES", {})
    with pytest.raises(ValueError, match="unknown trigger type: missing"):
        get("missing")


def test_alias_resolves_to_registered_trigger(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "_TRIGGERS", {})
    monkeypatch.setattr(registry, "_ALIASES", {})
    trigger = FakeTrigger()
    register(trigger)

    registry.register_alias("fake", "legacy_fake")

    assert get("legacy_fake") is trigger


def test_duplicate_alias_and_canonical_collision_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "_TRIGGERS", {})
    monkeypatch.setattr(registry, "_ALIASES", {})
    register(FakeTrigger())
    registry.register_alias("fake", "legacy_fake")

    with pytest.raises(ValueError, match="trigger alias already registered: legacy_fake"):
        registry.register_alias("fake", "legacy_fake")
    with pytest.raises(ValueError, match="trigger alias already registered: fake"):
        registry.register_alias("fake", "fake")


def test_register_requires_a_configuration_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "_TRIGGERS", {})

    class Unconfigured(FakeTrigger):
        configuration_model = cast("type[AutomationConfigurationBase]", dict)

    with pytest.raises(ValueError, match="must declare a configuration_model"):
        register(Unconfigured())


def test_register_requires_matching_trigger_type_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(registry, "_TRIGGERS", {})

    class Mismatched(FakeTrigger):
        configuration_model = MismatchedConfiguration

    with pytest.raises(ValueError, match="must default trigger_type to 'fake'"):
        register(Mismatched())


def test_registered_lists_built_in_triggers() -> None:
    assert {"issue", "github-cli-pull-requests", "azure-cli-pull-requests", "cron"} <= set(
        registry.registered()
    )
