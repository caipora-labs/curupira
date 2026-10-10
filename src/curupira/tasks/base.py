"""Abstract contracts shared by task triggers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from curupira.clients.process import AsyncProcessRunner
from curupira.models import PollingSettings, ResolvedAutomation, Task
from curupira.models.base import ValidatedModel
from curupira.models.templates import flatten_for_template
from curupira.storage import CronScheduleRepository, RunningSessionRepository

if TYPE_CHECKING:
    from curupira.models.configuration import AutomationConfigurationBase
    from curupira.vcs.base import VersionControl

PLUGIN_API_VERSION = 2


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
    """Shared services required to construct task feeds.

    Attributes:
        polling: Global discovery intervals and fetch limits.
        cron: Persistent cron schedule state.
        state_db_path: SQLite database shared by all durable state.
        runner: The only sanctioned way to start external processes.
    """

    polling: PollingSettings
    cron: CronScheduleRepository
    state_db_path: Path
    runner: AsyncProcessRunner = field(default_factory=AsyncProcessRunner)


@dataclass(frozen=True)
class TriggerState:
    """Durable state available to trigger lifecycle hooks.

    Attributes:
        sessions: Running coding-session snapshots used for resumption.
        cron: Persistent cron schedule state.
    """

    sessions: RunningSessionRepository
    cron: CronScheduleRepository


class Trigger(ABC):
    """Contract for a registered automation trigger type, built-in or plugin.

    Attributes:
        trigger_type: Value of ``trigger_type`` in the TOML that selects this trigger.
        configuration_model: Pydantic model validating this trigger's automation table.
        item_model: Pydantic model for discovered task payloads and prompt placeholders.
        api_version: Plugin API version the implementation was written against.
    """

    trigger_type: ClassVar[str]
    configuration_model: ClassVar[type[AutomationConfigurationBase]]
    item_model: ClassVar[type[ValidatedModel]]
    api_version: ClassVar[int] = PLUGIN_API_VERSION

    @classmethod
    def prompt_fields(cls) -> frozenset[str]:
        """Return placeholders supplied by this trigger's ``item_model`` fields."""
        return frozenset(cls.item_model.model_fields)

    def prompt_context(self, task: Task) -> dict[str, str]:
        """Flatten ``task.item`` into string placeholders for prompt templates."""
        return flatten_for_template(task.item)

    @abstractmethod
    def build_feed(
        self, automation: ResolvedAutomation, dependencies: FeedDependencies
    ) -> TaskFeed:
        """Construct a task feed for a resolved automation."""

    def validate_task(self, task: Task) -> None:
        """Reject task snapshots that this trigger could not have produced."""
        if task.scheduled_for is not None:
            raise ValueError("non-cron tasks must not contain a scheduled occurrence")

    def create_version_control(self, runner: AsyncProcessRunner) -> VersionControl | None:
        """Return a provider-specific clone mechanism, or None for native ``git clone``."""
        del runner
        return None

    async def on_task_started(self, task: Task, state: TriggerState) -> None:
        """Run after checkout, immediately before the coding agent starts."""
        del task, state

    async def on_task_finished(self, task: Task, state: TriggerState) -> None:
        """Release durable state once the coding agent exits."""
        await state.sessions.delete(task)
