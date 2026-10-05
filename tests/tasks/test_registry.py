"""Trigger registration and lookup contract tests."""

from __future__ import annotations

import pytest
from typing_extensions import override

import opscli.tasks.registry as registry
from opscli.feeds import TaskFeed
from opscli.models import ResolvedAutomation, Task
from opscli.tasks.base import FeedDependencies, Trigger
from opscli.tasks.registry import get, register


class FakeTrigger(Trigger):
    """Minimal implementation used to exercise the trigger registry."""

    trigger_type = "fake"

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
    with pytest.raises(ValueError, match="unknown trigger type: missing"):
        get("missing")
