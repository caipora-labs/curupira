"""Abstract contracts shared by task triggers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from opscli.clients.gh import GhClient
from opscli.models import PollingSettings, ResolvedAutomation, Task
from opscli.storage import CronScheduleRepository

if TYPE_CHECKING:
    from opscli.feeds import TaskFeed


@dataclass(frozen=True)
class FeedDependencies:
    """Shared services required to construct task feeds."""

    polling: PollingSettings
    gh: GhClient
    cron: CronScheduleRepository


class Trigger(ABC):
    """Contract for a registered automation trigger type."""

    trigger_type: ClassVar[str]

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
