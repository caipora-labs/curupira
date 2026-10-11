"""Behavioral tests for the reusable PtyTerminal Textual widget."""

from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console
from rich.text import Text
from textual.app import App, ComposeResult
from textual.events import Paste
from textual.widgets import Static
from typing_extensions import override

from curupira.tui.pty_terminal import PtyTerminal, default_pty_environment


class _FocusTarget(Static, can_focus=True):
    """Focusable sibling used to observe escape-key focus handoff."""


class _PtyHarness(App[None]):
    """Minimal Textual app that mounts one PtyTerminal under test."""

    CSS = """
    Screen { layout: vertical; }
    #other { height: 1; }
    PtyTerminal { width: 1fr; height: 1fr; }
    """

    def __init__(
        self,
        argv: list[str],
        *,
        cwd: Path | None = None,
        escape_key: str = "ctrl+g",
    ) -> None:
        super().__init__()
        self._argv = argv
        self._cwd = cwd
        self._escape_key = escape_key
        self.finished_codes: list[int] = []
        self.focus_released = False

    @override
    def compose(self) -> ComposeResult:
        yield _FocusTarget("other", id="other")
        yield PtyTerminal(
            self._argv,
            env=default_pty_environment(),
            cwd=self._cwd,
            escape_key=self._escape_key,
            id="pty",
        )

    def on_pty_terminal_finished(self, message: PtyTerminal.Finished) -> None:
        self.finished_codes.append(message.exit_code)

    def on_pty_terminal_focus_released(self, message: PtyTerminal.FocusReleased) -> None:
        del message
        self.focus_released = True
        self.query_one("#other", _FocusTarget).focus()


def _visible_text(terminal: PtyTerminal) -> str:
    return str(terminal.render())


async def _wait_until(predicate: Callable[[], bool], pilot: Any, *, attempts: int = 80) -> None:
    for _ in range(attempts):
        if predicate():
            return
        await pilot.pause(0.05)
    raise AssertionError("condition not met before timeout")


def test_default_pty_environment_is_allowlisted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("HOME", "/home/test")
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("USER", "tester")
    monkeypatch.setenv("SHELL", "/bin/bash")
    monkeypatch.setenv("SECRET", "nope")
    environment = default_pty_environment()
    assert environment["PATH"] == "/usr/bin"
    assert environment["HOME"] == "/home/test"
    assert environment["TERM"] == "xterm-256color"
    assert environment["COLORTERM"] == "truecolor"
    assert "SECRET" not in environment


def test_windows_guard_builds_unsupported_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(os, "name", "nt")
    terminal = PtyTerminal(["echo", "hi"])
    assert not terminal.supported
    assert "Windows" in str(terminal.render())


@pytest.mark.skipif(os.name != "posix", reason="PtyTerminal v1 requires POSIX")
@pytest.mark.asyncio
async def test_typed_input_echoes_through_cat() -> None:
    app = _PtyHarness(["cat"])
    async with app.run_test(size=(80, 24)) as pilot:
        terminal = app.query_one(PtyTerminal)
        terminal.focus()
        await _wait_until(lambda: terminal.pid is not None, pilot)
        await pilot.press("h", "i", "enter")
        await _wait_until(lambda: "hi" in _visible_text(terminal), pilot)
        assert "hi" in _visible_text(terminal)
        app.exit()


@pytest.mark.skipif(os.name != "posix", reason="PtyTerminal v1 requires POSIX")
@pytest.mark.asyncio
async def test_resize_updates_tput_cols_and_lines() -> None:
    app = _PtyHarness(
        [
            "bash",
            "-c",
            'while true; do printf \'%s %s\\n\' "$(tput cols)" "$(tput lines)"; sleep 0.05; done',
        ]
    )
    async with app.run_test(size=(60, 20)) as pilot:
        terminal = app.query_one(PtyTerminal)
        await _wait_until(lambda: terminal.content_size.width > 1, pilot)
        await pilot.pause(0.2)
        terminal._apply_winsize()
        expected = f"{terminal.content_size.width} {terminal.content_size.height}"
        await _wait_until(lambda: expected in _visible_text(terminal), pilot)

        await pilot.resize_terminal(100, 40)
        await pilot.pause(0.1)
        terminal._apply_winsize()
        expected = f"{terminal.content_size.width} {terminal.content_size.height}"
        await _wait_until(lambda: expected in _visible_text(terminal), pilot)
        assert expected in _visible_text(terminal)
        app.exit()


@pytest.mark.skipif(os.name != "posix", reason="PtyTerminal v1 requires POSIX")
@pytest.mark.asyncio
async def test_escape_key_releases_focus_and_ctrl_c_reaches_child(tmp_path: Path) -> None:
    marker = tmp_path / "sigint.txt"
    child = f"""
import signal, sys, pathlib, time
path = pathlib.Path({str(marker)!r})
path.write_text("ready")
def handle(signum, frame):
    path.write_text("interrupted")
    sys.exit(0)
signal.signal(signal.SIGINT, handle)
while True:
    time.sleep(0.05)
"""
    app = _PtyHarness([sys.executable, "-c", child])
    async with app.run_test(size=(80, 24)) as pilot:
        terminal = app.query_one(PtyTerminal)
        other = app.query_one("#other", _FocusTarget)
        terminal.focus()
        await _wait_until(lambda: terminal.has_focus, pilot)

        await pilot.press("ctrl+g")
        await _wait_until(lambda: app.focus_released and other.has_focus, pilot)
        assert not terminal.has_focus

        terminal.focus()
        await _wait_until(lambda: marker.exists() and marker.read_text() == "ready", pilot)
        await pilot.press("ctrl+c")
        await _wait_until(lambda: marker.read_text() == "interrupted", pilot)
        assert marker.read_text() == "interrupted"
        app.exit()


@pytest.mark.skipif(os.name != "posix", reason="PtyTerminal v1 requires POSIX")
@pytest.mark.asyncio
async def test_bracketed_paste_is_wrapped_when_child_enables_mode(tmp_path: Path) -> None:
    marker = tmp_path / "paste.bin"
    child = f"""
import os, sys, tty
sys.stdout.write("\\x1b[?2004hREADY\\n")
sys.stdout.flush()
tty.setraw(0)
data = os.read(0, 200)
open({str(marker)!r}, "wb").write(data)
"""
    app = _PtyHarness([sys.executable, "-c", child])
    async with app.run_test(size=(80, 24)) as pilot:
        terminal = app.query_one(PtyTerminal)
        terminal.focus()
        await _wait_until(lambda: "READY" in _visible_text(terminal), pilot)
        await _wait_until(
            lambda: terminal._emulator is not None and (2004 << 5) in terminal._emulator.mode,
            pilot,
        )
        terminal.on_paste(Paste("hello"))
        await _wait_until(lambda: marker.exists(), pilot)
        assert marker.read_bytes() == b"\x1b[200~hello\x1b[201~"
        app.exit()


@pytest.mark.skipif(os.name != "posix", reason="PtyTerminal v1 requires POSIX")
@pytest.mark.asyncio
async def test_child_exit_emits_finished_message() -> None:
    app = _PtyHarness(["bash", "-c", "exit 42"])
    async with app.run_test(size=(80, 24)) as pilot:
        await _wait_until(lambda: app.finished_codes == [42], pilot)
        terminal = app.query_one(PtyTerminal)
        assert terminal.finished_code == 42
        assert "42" in _visible_text(terminal)
        app.exit()


@pytest.mark.skipif(os.name != "posix", reason="PtyTerminal v1 requires POSIX")
@pytest.mark.asyncio
async def test_unmount_kills_and_reaps_child() -> None:
    app = _PtyHarness(["bash", "-c", "cat"])
    async with app.run_test(size=(80, 24)) as pilot:
        terminal = app.query_one(PtyTerminal)
        await _wait_until(lambda: terminal.pid is not None, pilot)
        pid = terminal.pid
        assert pid is not None
        os.kill(pid, 0)
        app.exit()
    for _ in range(40):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            break
        await asyncio.sleep(0.05)
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)

    def _reap() -> None:
        os.waitpid(pid, os.WNOHANG)

    with pytest.raises(ChildProcessError):
        await asyncio.to_thread(_reap)


@pytest.mark.skipif(os.name != "posix", reason="PtyTerminal v1 requires POSIX")
@pytest.mark.asyncio
async def test_write_and_restart_replace_running_child() -> None:
    app = _PtyHarness(["cat"])
    async with app.run_test(size=(80, 24)) as pilot:
        terminal = app.query_one(PtyTerminal)
        terminal.focus()
        await _wait_until(lambda: terminal.pid is not None, pilot)
        await pilot.pause(0.1)
        await pilot.press("p", "i", "n", "g", "enter")
        await _wait_until(lambda: "ping" in _visible_text(terminal), pilot)
        old_pid = terminal.pid
        assert old_pid is not None
        terminal.write("via-write\n")
        await _wait_until(lambda: "via-write" in _visible_text(terminal), pilot)
        terminal.restart()
        await _wait_until(lambda: terminal.pid is not None and terminal.pid != old_pid, pilot)
        assert terminal.pid != old_pid
        with pytest.raises(ProcessLookupError):
            os.kill(old_pid, 0)
        app.exit()


@pytest.mark.skipif(os.name != "posix", reason="PtyTerminal v1 requires POSIX")
@pytest.mark.asyncio
async def test_sgr_truecolor_and_alt_screen_sequences_render(tmp_path: Path) -> None:
    script = tmp_path / "sgr.py"
    script.write_text(
        "import sys\n"
        "sys.stdout.write('\\x1b[38;2;0;128;255mBLUE\\x1b[0m\\n')\n"
        "sys.stdout.write('\\x1b[?1049hALT\\x1b[?1049l')\n"
        "sys.stdout.write('DONE\\n')\n"
        "sys.stdout.flush()\n"
        "import time; time.sleep(0.5)\n",
        encoding="utf-8",
    )
    app = _PtyHarness([sys.executable, str(script)])
    async with app.run_test(size=(80, 24)) as pilot:
        terminal = app.query_one(PtyTerminal)
        await _wait_until(lambda: "DONE" in _visible_text(terminal), pilot)
        text = _visible_text(terminal)
        assert "DONE" in text
        assert "BLUE" in text
        rendered = terminal.render()
        assert isinstance(rendered, Text)
        console = Console(force_terminal=True, color_system="truecolor")
        blue_style = None
        for index, char in enumerate(rendered.plain):
            if char == "B":
                blue_style = rendered.get_style_at_offset(console, index)
                break
        assert blue_style is not None
        assert blue_style.color is not None
        assert blue_style.color.triplet is not None
        assert blue_style.color.triplet.blue == 255
        app.exit()
