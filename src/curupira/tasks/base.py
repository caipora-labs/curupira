"""Abstract contracts shared by task triggers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from curupira.clients.gh import GhClient
from curupira.models import PollingSettings, ResolvedAutomation, Task
from curupira.storage import CronScheduleRepository

if TYPE_CHECKING:
    from curupira.models.configuration import AutomationConfigurationBase


class TaskFeed(ABC):
    """Discovery interface shared by one-shot dispatch and continuous polling."""

    @abstractmethod
    async def poll(self, *, preview: bool = False) -> list[Task]:
        """Return tasks currently available; preview must not persist state."""

    @abstractmethod
    def stream(self) -> AsyncIterator[Task]:
        """Yield new tasks continuously with source-appropriate waits."""


class TaskSource(ABC):
    """Discover tasks for one automation without exposing provider commands."""

    @abstractmethod
    async def discover(self, automation: ResolvedAutomation, limit: int) -> list[Task]:
        """Return currently available tasks from this source."""


@dataclass(frozen=True)
class FeedDependencies:
    """Shared services required to construct task feeds."""

    polling: PollingSettings
    gh: GhClient
    cron: CronScheduleRepository


class Trigger(ABC):
    """Contract for one automation configuration shape and its task discovery."""

    trigger_type: ClassVar[str]
    configuration_type: ClassVar[type[AutomationConfigurationBase]]

    @classmethod
    @abstractmethod
    def prompt_fields(cls) -> frozenset[str]:
        """Return placeholders supplied specifically by this trigger."""

    @abstractmethod
    def prompt_context(self, task: Task) -> dict[str, str]:
        """Build values for this trigger's prompt placeholders."""

    @abstractmethod
    def build_feed(
        self, automation: ResolvedAutomation, dependencies: FeedDependencies
    ) -> TaskFeed:
        """Construct a task feed for a resolved automation."""
