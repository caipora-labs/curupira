"""Per-user runtime paths and process exclusivity."""

import errno
import os
from pathlib import Path
from typing import BinaryIO


def dispatch_home() -> Path:
    """Return the shared per-user gh-dispatch directory."""
    return Path.home() / ".gh-dispatch"


def default_config_path() -> Path:
    """Return the central default TOML settings path."""
    return dispatch_home() / "settings.toml"


def ensure_runtime_directories() -> None:
    """Create the central state and log directories with private permissions."""
    home = dispatch_home()
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    (home / "logs").mkdir(exist_ok=True, mode=0o700)


class InstanceAlreadyRunningError(RuntimeError):
    """Raised when another gh-dispatch process owns the shared dispatch lock."""


class DispatchInstanceLock:
    """Hold an operating-system file lock for one dispatching process."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._file: BinaryIO | None = None

    def acquire(self) -> None:
        """Acquire the lock without waiting for a running dispatcher to exit."""
        if self._file is not None:
            raise RuntimeError("instance lock is already acquired")

        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_file = self.path.open("a+b")
        try:
            if os.name == "nt":
                self._acquire_windows(lock_file)
            else:
                self._acquire_unix(lock_file)
        except OSError as error:
            lock_file.close()
            if error.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise InstanceAlreadyRunningError(
                    "another gh-dispatch process is already running"
                ) from error
            raise
        self._file = lock_file

    def release(self) -> None:
        """Release the OS lock and close its file descriptor."""
        if self._file is None:
            return
        lock_file, self._file = self._file, None
        try:
            if os.name == "nt":
                self._release_windows(lock_file)
            else:
                self._release_unix(lock_file)
        finally:
            lock_file.close()

    def __enter__(self) -> "DispatchInstanceLock":
        self.acquire()
        return self

    def __exit__(self, *_: object) -> None:
        self.release()

    @staticmethod
    def _acquire_unix(lock_file: BinaryIO) -> None:
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _release_unix(lock_file: BinaryIO) -> None:
        import fcntl

        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _acquire_windows(lock_file: BinaryIO) -> None:
        import msvcrt

        lock_file.seek(0, os.SEEK_END)
        if lock_file.tell() == 0:
            lock_file.write(b"\0")
            lock_file.flush()
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)

    @staticmethod
    def _release_windows(lock_file: BinaryIO) -> None:
        import msvcrt

        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
