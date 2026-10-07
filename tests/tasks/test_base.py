"""Tests for the abstract task discovery contracts."""

from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import cast

import pytest

from curupi.models import ResolvedAutomation, Task
from curupi.tasks.base import TaskFeed, TaskSource
from tests.helpers import issue_task, resolved_automation


class IncompleteFeed(TaskFeed):
    """A feed missing its required stream method."""

    async def poll(self, *, preview: bool = False) -> list[Task]:
        return []


class FakeFeed(TaskFeed):
    """Minimal concrete task feed."""

    async def poll(self, *, preview: bool = False) -> list[Task]:
        return [issue_task(Path())]

    def stream(self) -> AsyncIterator[Task]:
        async def tasks() -> AsyncIterator[Task]:
            yield issue_task(Path())

        return tasks()


class IncompleteSource(TaskSource):
    """A source missing its required discover method."""


class FakeSource(TaskSource):
    """Minimal concrete task source."""

    async def discover(self, automation: ResolvedAutomation, limit: int) -> list[Task]:
        return [issue_task(Path())][:limit]


def test_feed_requires_all_abstract_methods() -> None:
    """A TaskFeed subclass cannot omit a required method."""
    with pytest.raises(TypeError, match="stream"):
        cast(Callable[[], object], IncompleteFeed)()


def test_fake_feed_implements_contract() -> None:
    """A minimal implementation can be instantiated and used."""
    assert isinstance(FakeFeed(), TaskFeed)


def test_source_requires_discover_method() -> None:
    """A TaskSource subclass cannot omit discovery."""
    with pytest.raises(TypeError, match="discover"):
        cast(Callable[[], object], IncompleteSource)()


async def test_fake_source_implements_contract(tmp_path: Path) -> None:
    """A minimal implementation can be instantiated and used."""
    automation = resolved_automation(tmp_path)
    assert isinstance(FakeSource(), TaskSource)
    assert await FakeSource().discover(automation, 1)
