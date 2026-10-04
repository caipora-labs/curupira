"""Central runtime paths and process-lock behavior."""

from pathlib import Path

import pytest

from gh_dispatch.runtime import (
    DispatchInstanceLock,
    InstanceAlreadyRunningError,
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
