"""Feed construction and source-independent one-shot dispatch."""

from collections.abc import Callable

from curupi.agents import CliAdapterFactory, create_cli_adapter
from curupi.clients.gh import GhClient
from curupi.config import ApplicationSettings
from curupi.executor import TaskExecutor
from curupi.models import (
    DispatchOutcome,
    Task,
)
from curupi.storage import CronScheduleRepository, RunningSessionRepository
from curupi.tasks.base import FeedDependencies, TaskFeed
from curupi.tasks.registry import get as get_trigger
from curupi.telemetry import TaskTelemetry
from curupi.vcs.base import VersionControl
from curupi.vcs.github_cli import GitHubCliVersionControl


def create_task_feeds(
    settings: ApplicationSettings, gh: GhClient, cron: CronScheduleRepository
) -> list[TaskFeed]:
    """Build source-specific discovery using one resolved configuration snapshot."""
    feeds: list[TaskFeed] = []
    for automation in settings.resolve_automations().values():
        dependencies = FeedDependencies(settings.settings.polling, gh, cron)
        feeds.append(
            get_trigger(automation.configuration.trigger_type).build_feed(automation, dependencies)
        )
    return feeds


async def dispatch_next_task(
    settings: ApplicationSettings,
    gh: GhClient,
    *,
    dry_run: bool = False,
    adapter_factory: CliAdapterFactory = create_cli_adapter,
    version_control: VersionControl | None = None,
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
            version_control or GitHubCliVersionControl(),
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
