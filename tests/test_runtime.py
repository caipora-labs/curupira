"""Central runtime paths and process-lock behavior."""

import logging
from pathlib import Path

import pytest

from gh_dispatch.runtime import (
    DispatchInstanceLock,
    InstanceAlreadyRunningError,
    create_execution_log_handler,
    default_config_path,
    dispatch_home,
    ensure_runtime_directories,
)


def test_default_paths_use_the_user_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    assert dispatch_home() == tmp_path / ".gh-dispatch"
    assert default_config_path() == tmp_path / ".gh-dispatch" / "settings.toml"


def test_runtime_directories_create_central_logs_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    ensure_runtime_directories()

    assert (tmp_path / ".gh-dispatch" / "logs").is_dir()


def test_execution_log_handler_appends_to_central_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    logger = logging.getLogger("gh_dispatch.runtime_test")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for message in ("first task entry", "second task entry"):
        handler = create_execution_log_handler()
        logger.addHandler(handler)
        try:
            logger.info(message)
        finally:
            logger.removeHandler(handler)
            handler.close()

    log_path = tmp_path / ".gh-dispatch" / "logs" / "gh-dispatch.log"
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert "first task entry" in lines[0]
    assert "second task entry" in lines[1]
    assert lines[0][:4].isdigit()


def test_instance_lock_rejects_concurrent_process_and_can_be_reacquired(tmp_path: Path) -> None:
    path = tmp_path / "dispatch.lock"
    first = DispatchInstanceLock(path)
    second = DispatchInstanceLock(path)

    first.acquire()
    try:
        with pytest.raises(InstanceAlreadyRunningError):
            second.acquire()
    finally:
        first.release()

    second.acquire()
    second.release()
