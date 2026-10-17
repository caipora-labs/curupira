"""Process logging configuration and crash-report persistence."""

from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path

import pytest

from curupira import __version__
from curupira.logging_setup import (
    apply_log_level,
    configure_process_logging,
    install_crash_handlers,
    parse_log_level,
    persist_crash_report,
    resolve_log_level,
    uninstall_crash_handlers,
)
from curupira.models.configuration import ExecutionSettings
from curupira.runtime import create_execution_log_handler


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("debug", "DEBUG"),
        ("INFO", "INFO"),
        (" Warning ", "WARNING"),
        ("error", "ERROR"),
        ("CRITICAL", "CRITICAL"),
    ],
)
def test_parse_log_level_normalizes_names(raw: str, expected: str) -> None:
    assert parse_log_level(raw) == expected


def test_parse_log_level_rejects_unknown_values() -> None:
    with pytest.raises(ValueError, match="invalid log level"):
        parse_log_level("verbose")


def test_resolve_log_level_prefers_cli_override() -> None:
    assert resolve_log_level("INFO", None) == "INFO"
    assert resolve_log_level("INFO", "DEBUG") == "DEBUG"


def test_execution_settings_default_log_level_is_info() -> None:
    assert ExecutionSettings().log_level == "INFO"


def test_execution_settings_accepts_configured_log_level() -> None:
    settings = ExecutionSettings(log_level="DEBUG")
    assert settings.log_level == "DEBUG"


def test_execution_settings_rejects_invalid_log_level() -> None:
    with pytest.raises(Exception, match="log_level"):
        ExecutionSettings.model_validate({"log_level": "VERBOSE"})


def test_apply_log_level_updates_root_and_handlers() -> None:
    root = logging.getLogger()
    previous_level = root.level
    handler = logging.StreamHandler()
    previous_handler_level = handler.level
    root.addHandler(handler)
    try:
        apply_log_level("DEBUG")
        assert root.level == logging.DEBUG
        assert handler.level == logging.DEBUG
        apply_log_level("ERROR")
        assert root.level == logging.ERROR
        assert handler.level == logging.ERROR
    finally:
        root.removeHandler(handler)
        handler.close()
        root.setLevel(previous_level)
        for existing in root.handlers:
            existing.setLevel(previous_handler_level)


def test_configure_process_logging_and_file_handler_respect_level(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    previous_level = root.level
    for handler in previous_handlers:
        root.removeHandler(handler)
    try:
        configure_process_logging("DEBUG")
        file_handler = create_execution_log_handler("DEBUG")
        root.addHandler(file_handler)
        logging.getLogger("curupira.logging_setup_test").debug("debug-visible")
        file_handler.flush()
        log_path = tmp_path / ".curupira" / "logs" / "curupira.log"
        assert "debug-visible" in log_path.read_text(encoding="utf-8")
        assert (tmp_path / ".curupira" / "logs" / "crashes").is_dir()
    finally:
        for handler in list(root.handlers):
            root.removeHandler(handler)
            handler.close()
        for handler in previous_handlers:
            root.addHandler(handler)
        root.setLevel(previous_level)


def test_persist_crash_report_writes_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    try:
        raise RuntimeError("boom for investigation")
    except RuntimeError as error:
        path = persist_crash_report(
            type(error),
            error,
            error.__traceback__,
            context={"command": "run", "config": "/tmp/settings.toml"},
        )
    assert path is not None
    assert path.parent == tmp_path / ".curupira" / "logs" / "crashes"
    text = path.read_text(encoding="utf-8")
    assert f"curupira_version={__version__}" in text
    assert "exception_type=builtins.RuntimeError" in text
    assert "boom for investigation" in text
    assert "context.command='run'" in text
    assert "traceback:" in text
    assert "RuntimeError: boom for investigation" in text


def test_install_crash_handlers_persist_uncaught_exceptions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    previous_hook = sys.excepthook
    calls: list[tuple[type[BaseException], BaseException]] = []

    def capture(exc_type: type[BaseException], exc: BaseException, tb: object) -> None:
        calls.append((exc_type, exc))

    monkeypatch.setattr("curupira.logging_setup._previous_sys_excepthook", capture)
    uninstall_crash_handlers()
    try:
        install_crash_handlers()
        try:
            raise ValueError("uncaught")
        except ValueError as error:
            sys.excepthook(type(error), error, error.__traceback__)
        reports = list((tmp_path / ".curupira" / "logs" / "crashes").glob("crash-*.log"))
        assert len(reports) == 1
        assert "ValueError" in reports[0].read_text(encoding="utf-8")
        assert calls and calls[0][0] is ValueError
        assert (tmp_path / ".curupira" / "logs" / "faulthandler.log").is_file()
    finally:
        uninstall_crash_handlers()
        sys.excepthook = previous_hook


def test_crash_handlers_ignore_keyboard_interrupt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    uninstall_crash_handlers()
    try:
        install_crash_handlers()
        sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
        crashes = tmp_path / ".curupira" / "logs" / "crashes"
        assert not list(crashes.glob("crash-*.log")) if crashes.exists() else True
    finally:
        uninstall_crash_handlers()


def test_thread_excepthook_persists_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setattr("curupira.logging_setup._previous_threading_excepthook", lambda _args: None)
    uninstall_crash_handlers()
    try:
        install_crash_handlers()
        error = RuntimeError("thread boom")
        args = threading.ExceptHookArgs(
            (type(error), error, None, threading.current_thread())
        )
        threading.excepthook(args)
        reports = list((tmp_path / ".curupira" / "logs" / "crashes").glob("crash-*.log"))
        assert len(reports) == 1
        assert "thread boom" in reports[0].read_text(encoding="utf-8")
    finally:
        uninstall_crash_handlers()
