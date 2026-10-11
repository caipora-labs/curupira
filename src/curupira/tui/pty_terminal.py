"""Reusable Textual widget that hosts an interactive PTY child process.

``PtyTerminal`` is the building block for an embedded side-panel coding
assistant inside Curupira's Textual dashboard. This module does not wire the
widget into the orchestrator layout or configuration.

Platform support: Linux and macOS; Windows unsupported in v1. On Windows the
widget mounts a clear placeholder instead of raising at import time.

The child is spawned with ``pty.fork`` (session leader), driven by asyncio
``add_reader`` on the master fd, and emulated with ``pyte``. PTY bytes are never
logged. Process lifecycle cleanup runs in ``on_unmount`` (the App's teardown is
too late for reliable reaping) with an ``atexit`` safety net.

``pyte`` is LGPL-3.0 and is used as a dynamic dependency of this MIT-licensed
project. Throughput with the current reader loop is about 130 KB/s (a 5 MB flood
takes on the order of a minute) while the UI stays responsive; each ready
callback drains multiple large chunks up to a per-tick bound.
"""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import errno
import fcntl
import logging
import os
import signal
import struct
import sys
import time
import weakref
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import ClassVar

import pyte
from pyte import modes as pyte_modes
from rich.text import Text
from textual import events
from textual.app import RenderResult
from textual.binding import BindingType
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from typing_extensions import override

from curupira.tui.pty_keys import bracketed_paste_enabled, key_to_bytes, paste_to_bytes
from curupira.tui.pty_render import render_emulator

logger = logging.getLogger(__name__)

_DEFAULT_ENV_KEYS: tuple[str, ...] = ("PATH", "HOME", "LANG", "USER", "SHELL")
_DEFAULT_SCROLLBACK = 5_000
_REFRESH_INTERVAL_SECONDS = 1.0 / 30.0
_KILL_GRACE_SECONDS = 0.1
_NATURAL_EXIT_GRACE_SECONDS = 0.05
_SIGHUP_GRACE_SECONDS = 0.1
_READ_CHUNK_BYTES = 65_536
_MAX_READ_BYTES_PER_TICK = 512_000
_UNSUPPORTED_MESSAGE = "PTY terminals are not supported on Windows in v1."
_LIVE_TERMINALS: weakref.WeakSet[PtyTerminal] = weakref.WeakSet()
_ATEXIT_REGISTERED = False
_CHILD_RESET_SIGNALS: tuple[signal.Signals, ...] = (
    signal.SIGPIPE,
    signal.SIGINT,
    signal.SIGQUIT,
)


def default_pty_environment() -> dict[str, str]:
    """Build the default allowlisted environment for a PTY child.

    Returns:
        A copy of selected parent variables plus ``TERM`` and ``COLORTERM``.
    """
    environment = {
        key: value for key in _DEFAULT_ENV_KEYS if (value := os.environ.get(key)) is not None
    }
    environment["TERM"] = "xterm-256color"
    environment["COLORTERM"] = "truecolor"
    return environment


def clamp_terminal_dimensions(width: int, height: int) -> tuple[int, int]:
    """Clamp PTY columns/rows to at least 1x1 (including a zero content size)."""
    return max(1, width), max(1, height)


def _posix_supported() -> bool:
    """Return whether this interpreter can host a PTY child."""
    return os.name == "posix" and sys.platform != "win32"


def _atexit_cleanup() -> None:
    """Best-effort reaping if the process exits without unmounting widgets."""
    for terminal in list(_LIVE_TERMINALS):
        terminal._shutdown_child(grace_seconds=0.0)


def _ensure_atexit() -> None:
    """Register the process-wide PTY cleanup hook once."""
    global _ATEXIT_REGISTERED
    if _ATEXIT_REGISTERED:
        return
    atexit.register(_atexit_cleanup)
    _ATEXIT_REGISTERED = True


def _reset_child_signals() -> None:
    """Restore signals Python ignores so pipeline children receive SIGPIPE."""
    for sig in _CHILD_RESET_SIGNALS:
        with contextlib.suppress(OSError, ValueError, AttributeError):
            signal.signal(sig, signal.SIG_DFL)


class _EmulatorScreen(pyte.HistoryScreen):
    """History-backed pyte screen that replies to device-status queries."""

    def __init__(
        self,
        columns: int,
        lines: int,
        *,
        history: int,
        on_write: Callable[[bytes], None],
    ) -> None:
        super().__init__(columns, lines, history=history)
        self._on_write = on_write

    @override
    def write_process_input(self, data: str) -> None:
        """Forward DA/DSR replies to the PTY master."""
        self._on_write(data.encode("utf-8", errors="replace"))


class PtyTerminal(Widget, can_focus=True):
    """Focusable Textual widget hosting one interactive PTY child.

    Platform support: Linux and macOS; Windows unsupported in v1.

    Attributes:
        argv: Argument vector for the child (``argv[0]`` is the executable).
        env: Explicit environment allowlist for the child. When omitted, Curupira
            copies ``PATH``, ``HOME``, ``LANG``, ``USER``, and ``SHELL`` from the
            parent and sets ``TERM=xterm-256color`` plus ``COLORTERM=truecolor``.
        cwd: Optional working directory for the child.
        escape_key: Priority binding that releases focus instead of forwarding
            the chord to the child (default ``ctrl+g``).
    """

    DEFAULT_CSS = """
    PtyTerminal {
        background: #000000;
        color: #e0e0e0;
        overflow: hidden;
    }
    PtyTerminal:focus {
        border: tall #c8c8c8;
    }
    PtyTerminal.-unsupported {
        content-align: center middle;
        color: #ff5555;
        text-style: bold;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = []

    unsupported: reactive[bool] = reactive(False)
    finished_code: reactive[int | None] = reactive(None)

    class Finished(Message):
        """Posted when the PTY child exits.

        Attributes:
            exit_code: Process exit status, or ``-1`` when unavailable.
        """

        def __init__(self, exit_code: int) -> None:
            super().__init__()
            self.exit_code = exit_code

    class FocusReleased(Message):
        """Posted when the configured escape key releases focus."""

    def __init__(
        self,
        argv: Sequence[str],
        env: Mapping[str, str] | None = None,
        cwd: str | Path | None = None,
        *,
        escape_key: str = "ctrl+g",
        scrollback: int = _DEFAULT_SCROLLBACK,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Create a PTY terminal widget.

        Args:
            argv: Child argument vector; must be non-empty.
            env: Explicit environment mapping (allowlist). ``None`` selects the
                default allowlist from :func:`default_pty_environment`.
            cwd: Working directory for the child, or ``None`` for the parent cwd.
            escape_key: Key binding that returns focus to the host UI.
            scrollback: Bounded pyte history lines retained above the viewport.
            name: Optional Textual widget name.
            id: Optional Textual widget id.
            classes: Optional Textual CSS classes.
        """
        if not argv:
            raise ValueError("argv must contain at least the executable path")
        super().__init__(name=name, id=id, classes=classes)
        self._argv = tuple(argv)
        self._env = dict(env) if env is not None else default_pty_environment()
        self._env.setdefault("TERM", "xterm-256color")
        self._env.setdefault("COLORTERM", "truecolor")
        self._cwd = Path(cwd) if cwd is not None else None
        self._escape_key = escape_key
        self._scrollback = scrollback
        self._supported = _posix_supported()
        self.unsupported = not self._supported
        self._master_fd: int | None = None
        self._pid: int | None = None
        self._emulator: _EmulatorScreen | None = None
        self._stream: pyte.ByteStream | None = None
        self._render_dirty = False
        self._reader_installed = False
        self._shutting_down = False
        self._reap_task: asyncio.Task[None] | None = None
        self._placeholder = Text(_UNSUPPORTED_MESSAGE)
        self._bindings.bind(
            escape_key,
            "release_focus",
            description="Release focus",
            show=False,
            priority=True,
        )

    @property
    def supported(self) -> bool:
        """Whether this platform can spawn a PTY child."""
        return self._supported

    @property
    def pid(self) -> int | None:
        """Child process id while running, otherwise ``None``."""
        return self._pid

    @override
    def render(self) -> RenderResult:
        """Render the emulated buffer, optional exit footer, or placeholder."""
        if not self._supported:
            return self._placeholder
        if self._emulator is None:
            return self._placeholder
        cursor_visible = pyte_modes.DECTCEM in self._emulator.mode
        show_cursor = self.has_focus and cursor_visible and self.finished_code is None
        output = render_emulator(self._emulator, show_cursor=show_cursor)
        if self.finished_code is not None:
            output.append(f"\nProcess exited ({self.finished_code})", style="bold")
        return output

    def write(self, data: bytes | str) -> None:
        """Write bytes (or UTF-8 text) to the PTY master.

        Args:
            data: Payload forwarded to the child's stdin.
        """
        if self._master_fd is None:
            return
        payload = data.encode("utf-8") if isinstance(data, str) else data
        self._write_master(payload)

    def restart(self) -> None:
        """Kill the current child (if any) and spawn a fresh one."""
        if not self._supported:
            return
        self._shutdown_child(grace_seconds=_KILL_GRACE_SECONDS)
        self.finished_code = None
        self._spawn()

    def action_release_focus(self) -> None:
        """Handle the escape key: blur this widget and notify the host."""
        self.blur()
        self.post_message(self.FocusReleased())

    def on_mount(self) -> None:
        """Spawn the child on POSIX hosts and start render batching."""
        if not self._supported:
            self.add_class("-unsupported")
            self._placeholder = Text(_UNSUPPORTED_MESSAGE)
            return
        _ensure_atexit()
        _LIVE_TERMINALS.add(self)
        # Spawn after the first layout pass so the child does not start at a
        # transient 1x1 content size that scrolls early output out of view.
        self.call_after_refresh(self._spawn_after_layout)
        self.set_interval(_REFRESH_INTERVAL_SECONDS, self._flush_if_dirty, name="pty-refresh")

    def on_unmount(self) -> None:
        """Close the master, signal the process group, and reap the child."""
        self._shutdown_child(grace_seconds=_KILL_GRACE_SECONDS)
        _LIVE_TERMINALS.discard(self)

    def on_resize(self, event: events.Resize) -> None:
        """Resize the emulator and notify the child with ``SIGWINCH``."""
        del event
        self._apply_winsize()

    def on_key(self, event: events.Key) -> None:
        """Forward keystrokes to the child, except the escape binding."""
        if not self._supported or self._master_fd is None:
            return
        if event.key == self._escape_key:
            return
        modes = self._emulator.mode if self._emulator is not None else set()
        payload = key_to_bytes(event, modes=modes)
        if payload is None:
            return
        event.stop()
        event.prevent_default()
        self._write_master(payload)

    def on_paste(self, event: events.Paste) -> None:
        """Forward pasted text, wrapping it when mode 2004 is active."""
        if not self._supported or self._master_fd is None or self._emulator is None:
            return
        event.stop()
        event.prevent_default()
        bracketed = bracketed_paste_enabled(self._emulator.mode)
        self._write_master(paste_to_bytes(event.text, bracketed=bracketed))

    def _spawn_after_layout(self) -> None:
        """Spawn once the widget has a laid-out content size."""
        if self._pid is not None or self._emulator is not None:
            return
        self._spawn()

    def _spawn(self) -> None:
        """Fork a PTY session and exec ``argv`` in the child."""
        import pty

        self._cancel_reap_task()
        self._shutting_down = False
        columns, lines = self._content_dimensions()
        self._emulator = _EmulatorScreen(
            columns,
            lines,
            history=self._scrollback,
            on_write=self._write_master,
        )
        self._stream = pyte.ByteStream(self._emulator)
        self._render_dirty = True

        pid, master_fd = pty.fork()
        if pid == 0:
            self._child_exec()
            os._exit(127)

        self._pid = pid
        self._master_fd = master_fd
        os.set_blocking(master_fd, False)
        self._apply_winsize()
        self._install_reader()

    def _child_exec(self) -> None:
        """Run inside the forked child: reset signals/env and exec ``argv``."""
        try:
            _reset_child_signals()
            if self._cwd is not None:
                os.chdir(self._cwd)
            os.environ.clear()
            os.environ.update(self._env)
            os.execvp(self._argv[0], list(self._argv))
        except Exception:
            # Child must never unwind into the parent Textual process.
            os._exit(127)
        os._exit(127)

    def _install_reader(self) -> None:
        """Register the master fd with the asyncio event loop."""
        if self._master_fd is None or self._reader_installed:
            return
        loop = asyncio.get_running_loop()
        loop.add_reader(self._master_fd, self._on_master_readable)
        self._reader_installed = True

    def _remove_reader(self) -> None:
        """Drop the asyncio reader for the master fd."""
        if self._master_fd is None or not self._reader_installed:
            return
        with contextlib.suppress(RuntimeError, ValueError, OSError):
            asyncio.get_running_loop().remove_reader(self._master_fd)
        self._reader_installed = False

    def _on_master_readable(self) -> None:
        """Drain the master fd into pyte when the kernel signals readiness."""
        if self._master_fd is None or self._stream is None:
            return
        total = 0
        while total < _MAX_READ_BYTES_PER_TICK:
            try:
                chunk = os.read(self._master_fd, _READ_CHUNK_BYTES)
            except OSError as error:
                if error.errno in {errno.EAGAIN, errno.EWOULDBLOCK, errno.EINTR}:
                    break
                self._on_master_closed()
                return
            if not chunk:
                self._on_master_closed()
                return
            self._stream.feed(chunk)
            total += len(chunk)
        if total:
            self._render_dirty = True

    def _on_master_closed(self) -> None:
        """Handle EOF/EIO without blocking: close the master and reap async."""
        if self._shutting_down:
            return
        self._shutting_down = True
        self._remove_reader()
        master_fd = self._master_fd
        self._master_fd = None
        if master_fd is not None:
            with contextlib.suppress(OSError):
                os.close(master_fd)
        self._reap_task = asyncio.create_task(self._reap_after_master_closed())

    async def _reap_after_master_closed(self) -> None:
        """Poll for a natural exit, then escalate SIGHUP and SIGKILL."""
        pid = self._pid
        if pid is None:
            return
        exit_code = await self._poll_exit(pid, _NATURAL_EXIT_GRACE_SECONDS)
        if exit_code is None:
            self._signal_group(pid, signal.SIGHUP)
            exit_code = await self._poll_exit(pid, _SIGHUP_GRACE_SECONDS)
        if exit_code is None:
            self._signal_group(pid, signal.SIGKILL)
            exit_code = await self._poll_exit(pid, _KILL_GRACE_SECONDS)
        if exit_code is None:
            exit_code = -1
        self._pid = None
        self.finished_code = exit_code
        self.post_message(self.Finished(exit_code))
        self._render_dirty = True

    async def _poll_exit(self, pid: int, grace_seconds: float) -> int | None:
        """Poll ``waitpid(WNOHANG)`` until the child exits or grace elapses."""
        deadline = time.monotonic() + grace_seconds
        while True:
            reaped = self._try_reap(pid)
            if reaped is not None:
                return reaped
            if time.monotonic() >= deadline:
                return None
            await asyncio.sleep(0.01)

    def _flush_if_dirty(self) -> None:
        """Refresh the widget at most ~30 fps when the emulator changed."""
        if not self._render_dirty:
            return
        self._render_dirty = False
        self.refresh()

    def _content_dimensions(self) -> tuple[int, int]:
        """Return columns and rows from the border-exclusive content size."""
        size = self.content_size
        return clamp_terminal_dimensions(size.width, size.height)

    def _apply_winsize(self) -> None:
        """Resize pyte and push ``TIOCSWINSZ`` / ``SIGWINCH`` to the child."""
        if self._emulator is None:
            return
        columns, lines = self._content_dimensions()
        if columns != self._emulator.columns or lines != self._emulator.lines:
            self._emulator.resize(lines=lines, columns=columns)
            self._render_dirty = True
        if self._master_fd is None or self._pid is None:
            return
        packed = struct.pack("HHHH", lines, columns, 0, 0)
        try:
            fcntl.ioctl(self._master_fd, termios_tiocswinsz(), packed)
            os.kill(self._pid, signal.SIGWINCH)
        except OSError:
            logger.debug("Failed to deliver PTY window size to child pid=%s", self._pid)

    def _write_master(self, data: bytes) -> None:
        """Write to the master fd without logging payload bytes."""
        if self._master_fd is None or not data:
            return
        view = memoryview(data)
        while view:
            try:
                written = os.write(self._master_fd, view)
            except OSError as error:
                if error.errno in {errno.EAGAIN, errno.EWOULDBLOCK, errno.EINTR}:
                    return
                logger.debug("PTY master write failed for pid=%s", self._pid)
                return
            view = view[written:]

    def _cancel_reap_task(self) -> None:
        """Cancel an in-flight async reap when forcing shutdown or restart."""
        task = self._reap_task
        self._reap_task = None
        if task is not None and not task.done():
            task.cancel()

    def _shutdown_child(self, *, grace_seconds: float) -> int:
        """Force-close the master, signal the process group, and reap.

        Used for unmount, restart, and atexit. Natural EOF uses the async
        reap path instead so a normal exit code is not replaced by SIGKILL.

        Args:
            grace_seconds: Delay between ``SIGHUP`` and ``SIGKILL``.

        Returns:
            Exit code when known, otherwise ``-1``.
        """
        self._cancel_reap_task()
        self._shutting_down = True
        self._remove_reader()
        master_fd = self._master_fd
        self._master_fd = None
        if master_fd is not None:
            with contextlib.suppress(OSError):
                os.close(master_fd)

        pid = self._pid
        exit_code = -1
        if pid is not None:
            self._signal_group(pid, signal.SIGHUP)
            if grace_seconds > 0:
                deadline = time.monotonic() + grace_seconds
                while time.monotonic() < deadline:
                    reaped = self._try_reap(pid)
                    if reaped is not None:
                        exit_code = reaped
                        break
                    time.sleep(0.01)
            if exit_code == -1:
                self._signal_group(pid, signal.SIGKILL)
                reaped = self._try_reap(pid, block=True)
                if reaped is not None:
                    exit_code = reaped
        self._pid = None
        # Keep the last screen for display; restart replaces the emulator.
        self._stream = None
        return exit_code

    @staticmethod
    def _signal_group(pid: int, sig: signal.Signals) -> None:
        """Send ``sig`` to the child's process group, ignoring missing pids."""
        try:
            os.killpg(pid, sig)
        except ProcessLookupError:
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                return
        except PermissionError:
            logger.debug("Permission denied signaling PTY child pid=%s", pid)

    @staticmethod
    def _try_reap(pid: int, *, block: bool = False) -> int | None:
        """Reap ``pid`` and return its exit code when available."""
        flags = 0 if block else os.WNOHANG
        try:
            finished_pid, status = os.waitpid(pid, flags)
        except ChildProcessError:
            return -1
        if finished_pid == 0:
            return None
        return os.waitstatus_to_exitcode(status)


def termios_tiocswinsz() -> int:
    """Return ``TIOCSWINSZ`` from termios (lazy import for non-POSIX typing)."""
    import termios

    return termios.TIOCSWINSZ
