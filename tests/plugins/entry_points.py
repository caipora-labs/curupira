"""Fake installed distributions and entry points for plugin discovery tests."""

from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import EntryPoint

import curupira.plugins as plugins


@dataclass(frozen=True)
class FakeDistribution:
    name: str
    version: str


@dataclass(frozen=True)
class FakeEntryPoint:
    """Mimic an installed distribution's entry point without packaging metadata."""

    name: str
    value: str
    dist: FakeDistribution | None = FakeDistribution("curupira-ticket", "1.2.3")
    group: str = plugins.ENTRY_POINT_GROUP

    def load(self) -> object:
        return EntryPoint(self.name, self.value, self.group).load()


Install = Callable[..., None]
