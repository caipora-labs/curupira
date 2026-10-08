"""Abstract contracts shared by task triggers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import ClassVar

from curupira.clients.az import AzClient
from curupira.clients.gh import GhClient
from curupira.models import PollingSettings, ResolvedAutomation, Task
from curupira.storage import CronScheduleRepository


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
    az: AzClient
    cron: CronScheduleRepository


class Trigger(ABC):
    """Contract for a registered automation trigger type.

    ``trigger_type`` matches the ``Literal`` discriminator of the configuration model this
    trigger consumes; that model also declares the trigger's ``prompt_fields``.
    """

    trigger_type: ClassVar[str]

    @abstractmethod
    def prompt_context(self, task: Task) -> dict[str, str]:
        """Build values for the configuration model's trigger-specific placeholders."""

    @abstractmethod
    def build_feed(
        self, automation: ResolvedAutomation, dependencies: FeedDependencies
    ) -> TaskFeed:
        """Construct a task feed for a resolved automation."""


def pull_request_prompt_context(task: Task) -> dict[str, str]:
    """Map a pull-request task into the shared pull-request placeholders."""
    return {
        "pull_request_number": task.identity.id,
        "pull_request_title": task.title,
        "pull_request_body": task.body or "",
        "pull_request_url": task.url,
        "pull_request_is_draft": str(task.is_draft).lower() if task.is_draft is not None else "",
        "pull_request_head_ref": task.head_ref_name or "",
        "pull_request_base_ref": task.base_ref_name or "",
    }
