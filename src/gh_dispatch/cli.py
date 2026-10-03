"""Command-line entry points for configuration, one-shot dispatch, and polling."""

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

from gh_dispatch import __version__
from gh_dispatch.clients.gh import GhClient
from gh_dispatch.config import load_settings
from gh_dispatch.dispatcher import create_task_feeds, dispatch_next_task
from gh_dispatch.errors import DispatchError
from gh_dispatch.executor import TaskExecutor
from gh_dispatch.feeds import merge_task_streams
from gh_dispatch.models.base import ValidatedModel
from gh_dispatch.repositories import CronScheduleRepository, RunningSessionRepository
from gh_dispatch.scheduler import TaskScheduler


class CliOptions(ValidatedModel):
    """Validated command-line options."""

    command: Literal["validate", "run", "watch"]
    config: Path
    dry_run: bool = False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gh-dispatch",
        description="Dispatch GitHub and cron automations to native coding-agent CLIs.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("gh-dispatch.toml"),
        help="TOML configuration file (default: ./gh-dispatch.toml)",
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
    return parser


async def async_main(options: CliOptions) -> int:
    """Load validated settings and execute the selected CLI command."""
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
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    gh = GhClient()
    try:
        if options.command == "run":
            outcome = await dispatch_next_task(settings, gh, dry_run=options.dry_run)
            if outcome.selected is None:
                print("No matching task is currently available.")
                return 0
            selected = outcome.selected
            identity = selected.identity
            print(
                f"Selected {identity.automation_id}: "
                f"{identity.repo}#{identity.number}: {selected.title}"
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
        executor = TaskExecutor(settings.settings, gh, sessions, cron)
        scheduler = TaskScheduler(settings.settings, executor)
        tasks = merge_task_streams(
            [feed.stream() for feed in feeds], max_pending=settings.settings.max_pending_tasks
        )
        await scheduler.run(tasks, resume_sessions=recovered)
        return 1 if scheduler.failed_tasks else 0
    except (DispatchError, OSError, ValidationError) as error:
        print(f"Dispatch error: {error}", file=sys.stderr)
        return 1


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and own the application's event-loop lifecycle."""
    options = CliOptions.model_validate(vars(_build_parser().parse_args(argv)))
    try:
        return asyncio.run(async_main(options))
    except KeyboardInterrupt:
        return 130
