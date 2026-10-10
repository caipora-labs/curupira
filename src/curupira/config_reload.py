"""Hot-reload continuous dispatch when the configuration file changes."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path

from pydantic import ValidationError

from curupira.agents import CliAdapterFactory, create_cli_adapter
from curupira.config import ApplicationSettings, load_settings
from curupira.dispatcher import create_task_feeds
from curupira.errors import DispatchError
from curupira.executor import TaskExecutor
from curupira.models import Task
from curupira.scheduler import TaskScheduler
from curupira.storage import CronScheduleRepository, RunningSessionRepository
from curupira.tasks.feed import merge_task_streams
from curupira.telemetry import TaskTelemetry
from curupira.vcs.base import VersionControl

logger = logging.getLogger(__name__)

CONFIG_POLL_INTERVAL_SECONDS = 1.0
Sleep = Callable[[float], Awaitable[None]]
ActiveTasksCallback = Callable[[Sequence[Task]], None]
SettingsCallback = Callable[[ApplicationSettings], None]
SchedulerCallback = Callable[[TaskScheduler], None]


def config_mtime_ns(path: Path) -> int | None:
    """Return the configuration file mtime in nanoseconds, or ``None`` if missing."""
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def resolve_config_path(path: Path) -> Path:
    """Expand ``~`` and resolve the configuration path on a worker thread."""
    return path.expanduser().resolve()


async def wait_for_config_change(
    path: Path,
    *,
    since_mtime_ns: int | None,
    poll_interval_seconds: float = CONFIG_POLL_INTERVAL_SECONDS,
    sleep: Sleep = asyncio.sleep,
) -> int:
    """Block until the configuration file mtime differs from ``since_mtime_ns``.

    Returns:
        The new mtime in nanoseconds.
    """
    while True:
        current = await asyncio.to_thread(config_mtime_ns, path)
        if current is not None and current != since_mtime_ns:
            return current
        await sleep(poll_interval_seconds)


async def run_continuous_dispatch(
    settings: ApplicationSettings,
    config_path: Path,
    *,
    version_control: VersionControl | None = None,
    telemetry: TaskTelemetry | None = None,
    adapter_factory: CliAdapterFactory = create_cli_adapter,
    on_active_tasks_changed: ActiveTasksCallback | None = None,
    on_settings_reloaded: SettingsCallback | None = None,
    on_scheduler_ready: SchedulerCallback | None = None,
    poll_interval_seconds: float = CONFIG_POLL_INTERVAL_SECONDS,
    sleep: Sleep = asyncio.sleep,
) -> int:
    """Run watch-mode dispatch, reloading settings after in-flight work drains.

    When the configuration file changes, admission of new work stops. Tasks that
    are already running keep their resolved snapshots and finish. After every
    active task completes, settings and feeds are rebuilt from disk and
    discovery resumes with the latest configuration.
    """
    config_path = await asyncio.to_thread(resolve_config_path, config_path)
    current = settings
    mtime = await asyncio.to_thread(config_mtime_ns, config_path)
    failed_tasks = 0

    while True:
        sessions = RunningSessionRepository(current.settings.state_db_path)
        recovered = await sessions.list_all()
        cron = CronScheduleRepository(current.settings.state_db_path)
        feeds = create_task_feeds(current, cron)
        executor = TaskExecutor(
            current.settings,
            version_control,
            sessions,
            cron,
            adapter_factory=adapter_factory,
            telemetry=telemetry,
        )
        scheduler = TaskScheduler(
            current.settings,
            executor,
            on_active_tasks_changed=on_active_tasks_changed,
        )
        if on_scheduler_ready is not None:
            on_scheduler_ready(scheduler)

        tasks = merge_task_streams(
            [feed.stream() for feed in feeds],
            max_pending=current.settings.max_pending_tasks,
        )
        watcher = asyncio.create_task(
            _request_reload_on_change(
                config_path,
                scheduler,
                since_mtime_ns=mtime,
                poll_interval_seconds=poll_interval_seconds,
                sleep=sleep,
            ),
            name="curupira-config-reload-watch",
        )
        try:
            await scheduler.run(tasks, resume_sessions=recovered)
        finally:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)

        failed_tasks += scheduler.failed_tasks
        if not scheduler.reload_requested:
            return 1 if failed_tasks else 0

        logger.info(
            "Configuration file changed; reloading after in-flight tasks finished (%s)",
            config_path,
        )
        current, mtime = await _load_reloaded_settings(
            config_path,
            since_mtime_ns=mtime,
            poll_interval_seconds=poll_interval_seconds,
            sleep=sleep,
        )
        if on_settings_reloaded is not None:
            on_settings_reloaded(current)
        logger.info(
            "Configuration reloaded (%s automations; max active tasks: %s)",
            len(current.automations),
            current.settings.max_active_tasks,
        )


async def _request_reload_on_change(
    path: Path,
    scheduler: TaskScheduler,
    *,
    since_mtime_ns: int | None,
    poll_interval_seconds: float,
    sleep: Sleep,
) -> None:
    """Pause admission when the configuration file mtime changes."""
    await wait_for_config_change(
        path,
        since_mtime_ns=since_mtime_ns,
        poll_interval_seconds=poll_interval_seconds,
        sleep=sleep,
    )
    logger.info("Configuration file changed; pausing new admissions until in-flight tasks finish")
    scheduler.request_reload()


async def _load_reloaded_settings(
    path: Path,
    *,
    since_mtime_ns: int | None,
    poll_interval_seconds: float,
    sleep: Sleep,
) -> tuple[ApplicationSettings, int | None]:
    """Load settings, waiting for further file changes when the TOML is invalid."""
    mtime = since_mtime_ns
    while True:
        try:
            settings = await load_settings(path)
        except (OSError, ValueError, ValidationError, DispatchError) as error:
            logger.error(
                "Configuration reload failed: %s; waiting for the next change",
                error,
            )
            mtime = await wait_for_config_change(
                path,
                since_mtime_ns=mtime,
                poll_interval_seconds=poll_interval_seconds,
                sleep=sleep,
            )
            continue
        return settings, await asyncio.to_thread(config_mtime_ns, path)
