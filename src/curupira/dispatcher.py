"""Feed construction and source-independent one-shot dispatch."""

import logging
from collections.abc import Callable

from curupira.agents import CliAdapterFactory, create_cli_adapter
from curupira.clients.github_graphql import GitHubGraphQLClient
from curupira.clients.process import AsyncProcessRunner
from curupira.config import ApplicationSettings
from curupira.executor import TaskExecutor
from curupira.models import (
    DispatchOutcome,
    Task,
)
from curupira.storage import (
    CompletedTaskRepository,
    CronScheduleRepository,
    RunningSessionRepository,
)
from curupira.tasks.base import FeedDependencies, TaskFeed
from curupira.tasks.feed import poll_task_feeds
from curupira.tasks.registry import get as get_trigger
from curupira.tasks.revalidation import GitHubTaskRevalidator
from curupira.telemetry import TaskTelemetry
from curupira.vcs.base import VersionControl

logger = logging.getLogger(__name__)


def create_task_feeds(
    settings: ApplicationSettings,
    cron: CronScheduleRepository,
    *,
    runner: AsyncProcessRunner | None = None,
) -> list[TaskFeed]:
    """Build source-specific discovery using one resolved configuration snapshot."""
    dependencies = FeedDependencies(
        polling=settings.settings.polling,
        cron=cron,
        state_db_path=settings.settings.state_db_path,
        runner=runner or AsyncProcessRunner(),
    )
    return [
        get_trigger(automation.configuration.trigger_type).build_feed(automation, dependencies)
        for automation in settings.resolve_automations().values()
    ]


async def dispatch_next_task(
    settings: ApplicationSettings,
    *,
    dry_run: bool = False,
    adapter_factory: CliAdapterFactory = create_cli_adapter,
    version_control: VersionControl | None = None,
    telemetry: TaskTelemetry | None = None,
    on_task_selected: Callable[[Task], None] | None = None,
    runner: AsyncProcessRunner | None = None,
) -> DispatchOutcome:
    """Run the first currently available task, or preview it without any writes."""
    process_runner = runner or AsyncProcessRunner()
    cron = CronScheduleRepository(settings.settings.state_db_path)
    feeds = create_task_feeds(settings, cron, runner=process_runner)
    available = await poll_task_feeds(feeds, preview=dry_run)
    if dry_run:
        return DispatchOutcome(selected=available[0] if available else None)
    sessions = RunningSessionRepository(settings.settings.state_db_path)
    completed_tasks = CompletedTaskRepository(settings.settings.state_db_path)
    revalidate = GitHubTaskRevalidator(GitHubGraphQLClient(process_runner))
    executor = TaskExecutor(
        settings.settings,
        version_control,
        sessions,
        cron,
        adapter_factory=adapter_factory,
        telemetry=telemetry,
        runner=process_runner,
        pre_start_validator=revalidate,
    )
    for selected in available:
        current = await revalidate(selected)
        if current is None:
            await executor.discard_session(selected)
            await completed_tasks.delete(selected)
            continue
        completed = await completed_tasks.get(current)
        if completed is not None:
            if completed.fingerprint == current.state_fingerprint:
                await executor.discard_session(current)
                logger.info(
                    "Skipping unchanged completed task %s; next action: %s",
                    current.url,
                    completed.next_action,
                )
                continue
            await completed_tasks.delete(current)
        resumed = await sessions.get(current)
        if resumed is not None:
            if resumed.task.state_fingerprint != current.state_fingerprint:
                await executor.discard_session(resumed.task)
                resumed = None
                task = current
            else:
                task = resumed.task
        else:
            task = current
        if on_task_selected is not None:
            on_task_selected(task)
        result = await executor.execute(task, resumed)
        if result.returncode == 0:
            try:
                next_action = await revalidate.completion_next_action(task)
            except Exception as error:
                next_action = (
                    "Retry GitHub state validation before dispatching this completed snapshot "
                    f"(verification error: {type(error).__name__})."
                )
                logger.error(
                    "Could not verify completion for %s; next action: %s", task.url, next_action
                )
            if next_action is None:
                await completed_tasks.delete(task)
            else:
                await completed_tasks.save(task, next_action)
                logger.info("Task %s remains incomplete; next action: %s", task.url, next_action)
        return DispatchOutcome(selected=task, process=result)
    return DispatchOutcome(selected=None)
