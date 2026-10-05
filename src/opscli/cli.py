"""Command-line entry points for configuration, one-shot dispatch, and polling."""

import argparse
import asyncio
import logging
import sys
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from opscli import __version__
from opscli.clients.gh import GhClient
from opscli.config import load_settings
from opscli.dispatcher import create_task_feeds, dispatch_next_task
from opscli.errors import DispatchError
from opscli.executor import TaskExecutor
from opscli.models import Task
from opscli.models.base import ValidatedModel
from opscli.runtime import (
    DispatchInstanceLock,
    InstanceAlreadyRunningError,
    create_execution_log_handler,
    default_config_path,
    dispatch_home,
    ensure_runtime_directories,
)
from opscli.scheduler import TaskScheduler
from opscli.status import TerminalTaskStatus
from opscli.storage import CronScheduleRepository, RunningSessionRepository
from opscli.tasks.feed import merge_task_streams
from opscli.telemetry import TaskTelemetry
from opscli.tasks.base import TaskFeed


class CliOptions(ValidatedModel):
    """Validated command-line options."""

    command: Literal["validate", "run", "watch", "batch"]
    config: Path
    dry_run: bool = False
    size: int | None = None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="opscli",
        description="Dispatch GitHub and cron automations to native coding-agent CLIs.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--config",
        type=Path,
        default=default_config_path(),
        help="TOML configuration file (default: ~/.opscli/settings.toml)",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser(
        "validate", help="validate configuration without calling external CLIs or writing state"
    )
    run = subcommands.add_parser("run", help="execute one currently available automation task")
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="preview a task without reserving, persisting, cloning, or executing",
    )
    subcommands.add_parser("watch", help="poll all automations using the shared bounded scheduler")
    batch = subcommands.add_parser("batch", help="drain currently available automation tasks")
    batch.add_argument("--size", type=_positive_int, help="process at most N tasks")
    return parser


def _positive_int(value: str) -> int:
    """Parse a positive integer for bounded batch execution."""
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


async def _batch_stream(feeds: Sequence[TaskFeed], size: int | None) -> AsyncIterator[Task]:
    """Poll each feed until it has no newly available work, optionally capping admissions."""
    admitted = 0
    for feed in feeds:
        while size is None or admitted < size:
            tasks = await feed.poll()
            if not tasks:
                break
            for task in tasks:
                if size is not None and admitted >= size:
                    return
                admitted += 1
                yield task


async def async_main(options: CliOptions) -> int:
    """Load validated settings and execute the selected CLI command."""
    instance_lock: DispatchInstanceLock | None = None
    try:
        config_path = options.config.expanduser().resolve()
        if config_path == default_config_path().resolve():
            config_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if options.command in {"run", "watch", "batch"} and not options.dry_run:
            instance_lock = DispatchInstanceLock(dispatch_home() / "dispatch.lock")
            instance_lock.acquire()
            ensure_runtime_directories()
    except InstanceAlreadyRunningError as error:
        print(f"Dispatch error: {error}", file=sys.stderr)
        if instance_lock is not None:
            instance_lock.release()
        return 1
    except OSError as error:
        print(f"Runtime setup error: {error}", file=sys.stderr)
        if instance_lock is not None:
            instance_lock.release()
        return 1

    try:
        return await _execute_command(options)
    finally:
        if instance_lock is not None:
            instance_lock.release()


async def _execute_command(options: CliOptions) -> int:
    """Run a validated command after acquiring any required process lock."""
    try:
        settings = await load_settings(options.config)
    except (OSError, ValueError) as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2
    if options.command == "validate":
        count = len(settings.coding_agents.automations)
        limit = settings.settings.max_active_tasks
        print(f"Configuration is valid ({count} automations; max active tasks: {limit}).")
        return 0
    telemetry = TaskTelemetry(
        str(settings.settings.otlp_endpoint)
        if settings.settings.otlp_endpoint is not None
        else None
    )
    log_handler: logging.FileHandler | None = None
    root_logger = logging.getLogger()
    try:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
        if options.command in {"watch", "batch"} or not options.dry_run:
            log_handler = create_execution_log_handler()
            root_logger.setLevel(logging.INFO)
            root_logger.addHandler(log_handler)
        gh = GhClient()
        if options.command == "run":
            status = TerminalTaskStatus()
            try:
                outcome = await dispatch_next_task(
                    settings,
                    gh,
                    dry_run=options.dry_run,
                    telemetry=telemetry,
                    on_task_selected=lambda task: status.update(
                        (task,), settings.settings.max_active_tasks
                    ),
                )
            finally:
                status.clear()
            if outcome.selected is None:
                print("No matching task is currently available.")
                return 0
            selected = outcome.selected
            identity = selected.identity
            print(
                f"Selected {identity.automation_id}: "
                f"{identity.repo}#{identity.id}: {selected.title}"
            )
            print(selected.url)
            if options.dry_run:
                print("Dry run: no task was reserved or executed.")
            elif outcome.process is not None:
                if outcome.process.stdout:
                    print(outcome.process.stdout)
                if outcome.process.stderr:
                    print(outcome.process.stderr, file=sys.stderr)
                return outcome.process.returncode
            return 0
        sessions = RunningSessionRepository(settings.settings.state_db_path)
        recovered = await sessions.list_all()
        cron = CronScheduleRepository(settings.settings.state_db_path)
        feeds = create_task_feeds(settings, gh, cron)
        executor = TaskExecutor(settings.settings, gh, sessions, cron, telemetry=telemetry)
        status = TerminalTaskStatus(show_idle=True)
        scheduler = TaskScheduler(
            settings.settings,
            executor,
            on_active_tasks_changed=lambda tasks: status.update(
                tasks, settings.settings.max_active_tasks
            ),
        )
        if options.command == "batch":
            tasks = _batch_stream(feeds, options.size)
        else:
            tasks = merge_task_streams(
                [feed.stream() for feed in feeds], max_pending=settings.settings.max_pending_tasks
            )
        try:
            await scheduler.run(tasks, resume_sessions=recovered)
        finally:
            status.clear()
        return 1 if scheduler.failed_tasks else 0
    except (DispatchError, OSError, ValidationError) as error:
        print(f"Dispatch error: {error}", file=sys.stderr)
        return 1
    finally:
        try:
            telemetry.shutdown()
        finally:
            if log_handler is not None:
                root_logger.removeHandler(log_handler)
                log_handler.close()


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and own the application's event-loop lifecycle."""
    options = CliOptions.model_validate(vars(_build_parser().parse_args(argv)))
    try:
        return asyncio.run(async_main(options))
    except KeyboardInterrupt:
        return 130
