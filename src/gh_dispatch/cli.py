"""Command-line interface for gh-dispatch."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from gh_dispatch.clients.gh import GhClient
from gh_dispatch.config import load_settings
from gh_dispatch.cron import CronWatcher
from gh_dispatch.dispatcher import dispatch_next_issue
from gh_dispatch.errors import DispatchError
from gh_dispatch.repositories import CronScheduleRepository, RunningSessionRepository
from gh_dispatch.scheduler import CoreScheduler
from gh_dispatch.watcher import IssueWatcher, PullRequestWatcher, merge_task_streams


class CliOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    command: Literal["validate", "run", "watch"]
    config: Path
    dry_run: bool = False


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gh-dispatch",
        description="Watch GitHub issues and pull requests and run coding-agent tasks.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("gh-dispatch.toml"),
        help="TOML configuration file (default: ./gh-dispatch.toml)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("validate", help="validate configuration without calling CLIs")
    run_parser = subparsers.add_parser("run", help="find an issue and start its coding agent")
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show the selected issue without starting its coding agent",
    )
    subparsers.add_parser("watch", help="poll issues and run bounded concurrent tasks")
    return parser


async def async_main(options: CliOptions) -> int:
    try:
        settings = await load_settings(options.config)
    except (OSError, ValueError, ValidationError, tomllib.TOMLDecodeError) as error:
        print(f"Configuration error: {error}", file=sys.stderr)
        return 2

    if options.command == "validate":
        repository_count = len(settings.watchers.issues.repositories)
        if settings.watchers.pull_requests is not None:
            repository_count += len(settings.watchers.pull_requests.repositories)
        cron_job_count = len(settings.watchers.cron.jobs) if settings.watchers.cron else 0
        details = f"{repository_count} watcher repositories"
        if cron_job_count:
            noun = "cron job" if cron_job_count == 1 else "cron jobs"
            details += f"; {cron_job_count} {noun}"
        print(
            "Configuration is valid "
            f"({details}; max active tasks: {settings.core.max_active_tasks})."
        )
        return 0

    if options.command == "watch":
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )
        gh = GhClient()
        session_repository = RunningSessionRepository(settings.core.state_db_path)
        recovered_sessions = await session_repository.list_all()
        has_recovered_cron = any(session.task.task_type == "cron" for session in recovered_sessions)
        cron_repository = (
            CronScheduleRepository(settings.core.state_db_path)
            if settings.watchers.cron is not None or has_recovered_cron
            else None
        )
        streams = [
            IssueWatcher(
                settings.watchers.issues,
                gh,
                workspace_dir=settings.core.workspace_dir,
            ).watch()
        ]
        if settings.watchers.pull_requests is not None:
            streams.append(
                PullRequestWatcher(
                    settings.watchers.pull_requests,
                    gh,
                    workspace_dir=settings.core.workspace_dir,
                ).watch()
            )
        if settings.watchers.cron is not None and cron_repository is not None:
            streams.append(
                CronWatcher(
                    settings.watchers.cron,
                    cron_repository,
                    workspace_dir=settings.core.workspace_dir,
                ).watch()
            )
        scheduler = CoreScheduler(
            settings.core,
            settings.agent,
            settings.coding_agents,
            gh,
            session_repository,
            cron_repository=cron_repository,
        )
        tasks = merge_task_streams(
            streams,
            max_pending=settings.core.max_active_tasks,
        )
        try:
            await scheduler.run(tasks, resume_sessions=recovered_sessions)
        except DispatchError as error:
            print(f"Dispatch error: {error}", file=sys.stderr)
            return 1
        return 0

    session_repository = RunningSessionRepository(settings.core.state_db_path)
    try:
        outcome = await dispatch_next_issue(
            settings,
            GhClient(),
            dry_run=options.dry_run,
            session_repository=session_repository,
        )
    except DispatchError as error:
        print(f"Dispatch error: {error}", file=sys.stderr)
        return 1

    if outcome.selected is None:
        print("No matching issue found.")
        return 0

    repository = outcome.selected.repository.repo
    selected = outcome.selected
    print(f"Selected {repository}#{selected.number}: {selected.title}")
    print(selected.url)

    if options.dry_run:
        print("Dry run: the coding agent was not started.")
        return 0

    return outcome.process.returncode if outcome.process is not None else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments and start the asynchronous application."""
    namespace = _build_parser().parse_args(argv)
    options = CliOptions.model_validate(vars(namespace))
    try:
        return asyncio.run(async_main(options))
    except KeyboardInterrupt:
        return 130
