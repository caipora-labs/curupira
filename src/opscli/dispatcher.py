"""Feed construction and source-independent one-shot dispatch."""

from collections.abc import Callable

from opscli.agents import CliAdapterFactory, create_cli_adapter
from opscli.clients.gh import GhClient
from opscli.config import ApplicationSettings
from opscli.executor import TaskExecutor
from opscli.models import (
    CronAutomationConfiguration,
    DispatchOutcome,
    IssueAutomationConfiguration,
    PullRequestAutomationConfiguration,
    Task,
)
from opscli.storage import CronScheduleRepository, RunningSessionRepository
from opscli.tasks.base import FeedDependencies, TaskFeed
from opscli.tasks.cron import CronTaskFeed
from opscli.tasks.github_issues import IssueTrigger
from opscli.tasks.github_pull_requests import PullRequestTrigger
from opscli.telemetry import TaskTelemetry


def create_task_feeds(
    settings: ApplicationSettings, gh: GhClient, cron: CronScheduleRepository
) -> list[TaskFeed]:
    """Build source-specific discovery using one resolved configuration snapshot."""
    feeds: list[TaskFeed] = []
    for automation in settings.resolve_automations().values():
        if isinstance(automation.configuration, CronAutomationConfiguration):
            feeds.append(CronTaskFeed(automation, settings.settings.polling, cron))
        elif isinstance(automation.configuration, IssueAutomationConfiguration):
            feeds.append(
                IssueTrigger().build_feed(
                    automation,
                    FeedDependencies(settings.settings.polling, gh, cron),
                )
            )
        elif isinstance(automation.configuration, PullRequestAutomationConfiguration):
            feeds.append(
                PullRequestTrigger().build_feed(
                    automation,
                    FeedDependencies(settings.settings.polling, gh, cron),
                )
            )
        else:
            raise ValueError(f"unsupported trigger type: {automation.configuration.trigger_type}")
    return feeds


async def dispatch_next_task(
    settings: ApplicationSettings,
    gh: GhClient,
    *,
    dry_run: bool = False,
    adapter_factory: CliAdapterFactory = create_cli_adapter,
    telemetry: TaskTelemetry | None = None,
    on_task_selected: Callable[[Task], None] | None = None,
) -> DispatchOutcome:
    """Run the first currently available task, or preview it without any writes."""
    cron = CronScheduleRepository(settings.settings.state_db_path)
    feeds = create_task_feeds(settings, gh, cron)
    for feed in feeds:
        available = await feed.poll(preview=dry_run)
        if not available:
            continue
        selected = available[0]
        if dry_run:
            return DispatchOutcome(selected=selected)
        sessions = RunningSessionRepository(settings.settings.state_db_path)
        resumed = await sessions.get(selected)
        executor = TaskExecutor(
            settings.settings,
            gh,
            sessions,
            cron,
            adapter_factory=adapter_factory,
            telemetry=telemetry,
        )
        task = resumed.task if resumed is not None else selected
        if on_task_selected is not None:
            on_task_selected(task)
        result = await executor.execute(task, resumed)
        return DispatchOutcome(selected=task, process=result)
    return DispatchOutcome(selected=None)
