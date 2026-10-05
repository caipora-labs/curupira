"""Trigger registration and lookup contract tests."""

from __future__ import annotations

from typing_extensions import override

import pytest

from gh_dispatch.feeds import TaskFeed
from gh_dispatch.models import ResolvedAutomation, Task
from gh_dispatch.tasks.base import FeedDependencies, Trigger
from gh_dispatch.tasks.registry import get, register


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


def test_register_and_get_trigger() -> None:
    trigger = FakeTrigger()

    register(trigger)

    assert get("fake") is trigger


def test_register_duplicate_trigger_type_raises() -> None:
    register(FakeTrigger())

    with pytest.raises(ValueError, match="trigger type already registered: fake"):
        register(FakeTrigger())


def test_get_unknown_trigger_type_raises() -> None:
    with pytest.raises(ValueError, match="unknown trigger type: missing"):
        get("missing")
