"""Trigger registration and lookup contract tests."""

from __future__ import annotations

from typing import get_args

import pytest
from typing_extensions import override

from curupira.models import AutomationConfiguration, ResolvedAutomation, Task
from curupira.tasks import registry
from curupira.tasks.base import FeedDependencies, TaskFeed, Trigger
from curupira.tasks.registry import get, register


class FakeTrigger(Trigger):
    """Minimal implementation used to exercise the trigger registry."""

    trigger_type = "fake"

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
    with pytest.raises(ValueError, match="unknown trigger type: missing"):
        get("missing")


def test_every_configuration_discriminator_has_one_registered_trigger() -> None:
    import curupira.tasks  # noqa: F401  (registers the concrete triggers)

    union = get_args(get_args(AutomationConfiguration)[0])
    discriminators = {
        value
        for model in union
        for value in get_args(model.model_fields["trigger_type"].annotation)
    }

    assert discriminators == registry.registered_types()
