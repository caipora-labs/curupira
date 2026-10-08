"""An installable-style trigger plugin that imports only the public plugin API."""

from typing import Literal

from typing_extensions import override

from curupira.models import IssueAutomationConfiguration
from curupira.plugins import (
    AsyncProcessRunner,
    AutomationConfigurationBase,
    FeedDependencies,
    NonEmptyString,
    PollingTaskFeed,
    ResolvedAutomation,
    Task,
    TaskFeed,
    TaskIdentity,
    TaskSource,
    Trigger,
    TriggerState,
    VersionControl,
)


class TicketAutomationConfiguration(AutomationConfigurationBase):
    """Discover tickets from one project of an external tracker.

    Attributes:
        project: Tracker project key.
        priority: Minimum ticket priority.
    """

    trigger_type: Literal["ticket"] = "ticket"
    project: NonEmptyString
    priority: Literal["low", "high"] = "low"


class TicketSource(TaskSource):
    """Return tickets configured on the trigger instead of calling a tracker."""

    def __init__(self, tickets: list[tuple[str, str]]) -> None:
        self._tickets = tickets

    @override
    async def discover(self, automation: ResolvedAutomation, limit: int) -> list[Task]:
        config = automation.configuration
        if not isinstance(config, TicketAutomationConfiguration):
            raise ValueError("ticket source requires a ticket configuration")
        return [
            Task(
                identity=TaskIdentity(
                    automation_id=automation.automation_id,
                    repo=config.repo,
                    task_type="ticket",
                    id=key,
                ),
                automation=automation,
                title=f"Ticket {key}",
                url=f"https://tracker.example/{config.project}/{key}",
                attributes={"priority": priority},
            )
            for key, priority in self._tickets[:limit]
        ]


class TicketTrigger(Trigger):
    """Trigger for ticket automations that records its lifecycle calls."""

    trigger_type = "ticket"
    configuration_model = TicketAutomationConfiguration

    def __init__(self) -> None:
        self.tickets: list[tuple[str, str]] = []
        self.events: list[str] = []
        self.version_control: VersionControl | None = None

    @classmethod
    @override
    def prompt_fields(cls) -> frozenset[str]:
        return frozenset({"ticket_key", "ticket_priority"})

    @override
    def prompt_context(self, task: Task) -> dict[str, str]:
        return {"ticket_key": task.identity.id, "ticket_priority": task.attributes["priority"]}

    @override
    def build_feed(
        self, automation: ResolvedAutomation, dependencies: FeedDependencies
    ) -> TaskFeed:
        return PollingTaskFeed(automation, dependencies.polling, TicketSource(self.tickets))

    @override
    def create_version_control(self, runner: AsyncProcessRunner) -> VersionControl | None:
        return self.version_control

    @override
    async def on_task_started(self, task: Task, state: TriggerState) -> None:
        self.events.append(f"started:{task.identity.id}")

    @override
    async def on_task_finished(self, task: Task, state: TriggerState) -> None:
        self.events.append(f"finished:{task.identity.id}")
        await super().on_task_finished(task, state)


class FutureTrigger(TicketTrigger):
    """A plugin written against an unsupported plugin API."""

    api_version = 2


class DuplicateIssueTrigger(TicketTrigger):
    """A plugin that tries to replace a built-in trigger type."""

    trigger_type = "issue"
    configuration_model = IssueAutomationConfiguration


class BrokenTrigger(TicketTrigger):
    """A plugin whose constructor fails."""

    def __init__(self) -> None:
        raise RuntimeError("tracker token missing")


ticket_trigger = TicketTrigger()
NOT_A_TRIGGER = 42
