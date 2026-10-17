"""Configure process logging and persist crash diagnostics."""

from __future__ import annotations

import contextlib
import faulthandler
import logging
import os
import platform
import sys
import threading
import traceback
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import TextIO

from curupira import __version__
from curupira.models.configuration import LogLevel
from curupira.runtime import dispatch_home, ensure_runtime_directories

_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_LEVEL_BY_NAME: dict[str, LogLevel] = {
    "DEBUG": "DEBUG",
    "INFO": "INFO",
    "WARNING": "WARNING",
    "ERROR": "ERROR",
    "CRITICAL": "CRITICAL",
}
_NUMERIC_LEVEL: dict[LogLevel, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

_fault_file: TextIO | None = None
_previous_sys_excepthook = sys.excepthook
_previous_threading_excepthook = threading.excepthook
_crash_handlers_installed = False


def parse_log_level(value: str) -> LogLevel:
    """Normalize a CLI or TOML log-level string to a validated name."""
    normalized = value.strip().upper()
    try:
        return _LEVEL_BY_NAME[normalized]
    except KeyError as error:
        allowed = ", ".join(_LEVEL_BY_NAME)
        raise ValueError(f"invalid log level {value!r}; expected one of: {allowed}") from error


def resolve_log_level(
    configured: LogLevel,
    cli_override: LogLevel | None = None,
) -> LogLevel:
    """Prefer an explicit CLI override over ``[settings].log_level``."""
    return configured if cli_override is None else cli_override


def logging_level_value(level: LogLevel) -> int:
    """Map a Curupira log-level name to the stdlib numeric level."""
    return _NUMERIC_LEVEL[level]


def apply_log_level(level: LogLevel) -> None:
    """Set the root logger level used by console, file, and TUI handlers."""
    root = logging.getLogger()
    numeric = logging_level_value(level)
    root.setLevel(numeric)
    for handler in root.handlers:
        handler.setLevel(numeric)


def configure_process_logging(level: LogLevel) -> None:
    """Install a stderr handler when none exists, then apply ``level``."""
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=logging_level_value(level), format=_LOG_FORMAT)
    apply_log_level(level)


def crash_reports_dir() -> Path:
    """Return the directory that stores persisted crash reports."""
    ensure_runtime_directories()
    path = dispatch_home() / "logs" / "crashes"
    path.mkdir(exist_ok=True, mode=0o700)
    return path


def persist_crash_report(
    exc_type: type[BaseException],
    exc: BaseException,
    tb: TracebackType | None,
    *,
    context: Mapping[str, object] | None = None,
    thread_name: str | None = None,
) -> Path | None:
    """Write a detailed crash report under ``~/.curupira/logs/crashes/``.

    Returns:
        The written path, or ``None`` when the report could not be persisted.
    """
    try:
        report_dir = crash_reports_dir()
        stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        path = report_dir / f"crash-{stamp}-{os.getpid()}.log"
        lines = [
            f"timestamp={datetime.now(tz=UTC).isoformat()}",
            f"curupira_version={__version__}",
            f"python_version={sys.version.replace(chr(10), ' ')}",
            f"platform={platform.platform()}",
            f"executable={sys.executable}",
            f"argv={list(sys.argv)!r}",
            f"pid={os.getpid()}",
            f"thread={thread_name or threading.current_thread().name}",
            f"exception_type={exc_type.__module__}.{exc_type.__qualname__}",
            f"exception_message={exc}",
        ]
        if context:
            for key, value in context.items():
                lines.append(f"context.{key}={value!r}")
        lines.append("")
        lines.append("traceback:")
        lines.extend(traceback.format_exception(exc_type, exc, tb))
        path.write_text("\n".join(lines), encoding="utf-8")
        with contextlib.suppress(OSError):
            path.chmod(0o600)
        logging.getLogger(__name__).critical(
            "Crash report written to %s (%s: %s)",
            path,
            exc_type.__name__,
            exc,
        )
        return path
    except OSError as error:
        logging.getLogger(__name__).error("Could not persist crash report: %s", error)
        return None


def _handle_uncaught_exception(
    exc_type: type[BaseException],
    exc: BaseException,
    tb: TracebackType | None,
) -> None:
    """Persist diagnostics for an uncaught main-thread exception, then chain."""
    if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
        _previous_sys_excepthook(exc_type, exc, tb)
        return
    persist_crash_report(exc_type, exc, tb)
    _previous_sys_excepthook(exc_type, exc, tb)


def _handle_thread_exception(args: threading.ExceptHookArgs) -> None:
    """Persist diagnostics for an uncaught thread exception, then chain."""
    exc_type = args.exc_type
    exc = args.exc_value
    tb = args.exc_traceback
    if exc is None or issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
        _previous_threading_excepthook(args)
        return
    persist_crash_report(
        exc_type,
        exc,
        tb,
        thread_name=args.thread.name if args.thread is not None else None,
    )
    _previous_threading_excepthook(args)


def enable_fault_handler() -> None:
    """Dump fatal interpreter faults into the central logs directory."""
    global _fault_file
    if _fault_file is not None:
        return
    ensure_runtime_directories()
    fault_path = dispatch_home() / "logs" / "faulthandler.log"
    _fault_file = fault_path.open("a", encoding="utf-8")
    with contextlib.suppress(OSError):
        fault_path.chmod(0o600)
    faulthandler.enable(file=_fault_file, all_threads=True)


def install_crash_handlers() -> None:
    """Install process-wide crash persistence and fatal-signal dumps."""
    global _crash_handlers_installed
    if _crash_handlers_installed:
        return
    enable_fault_handler()
    sys.excepthook = _handle_uncaught_exception
    threading.excepthook = _handle_thread_exception
    _crash_handlers_installed = True


def uninstall_crash_handlers() -> None:
    """Restore previous exception hooks and close the faulthandler file."""
    global _crash_handlers_installed, _fault_file
    if not _crash_handlers_installed:
        return
    sys.excepthook = _previous_sys_excepthook
    threading.excepthook = _previous_threading_excepthook
    faulthandler.disable()
    if _fault_file is not None:
        _fault_file.close()
        _fault_file = None
    _crash_handlers_installed = False
