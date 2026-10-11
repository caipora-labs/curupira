"""Textual pilot tests for the embedded TUI assistant side panel."""

from __future__ import annotations

import os
import sys
import time
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar, Literal

import pytest
from textual.widgets import OptionList, RichLog
from typing_extensions import override

from curupira.agents.base import CodingAgentCliAdapter
from curupira.agents.interactive import InteractiveLaunchSpec
from curupira.config import ApplicationSettings
from curupira.models import CliProfileBase, CodingTaskRequest
from curupira.telemetry import TaskTelemetry
from curupira.tui.app import HelpScreen, OrchestratorApp
from curupira.tui.assistant_panel import AssistantPanel
from curupira.tui.pty_terminal import PtyTerminal
from curupira.vcs.git_cli import NativeGitVersionControl
from tests.helpers import settings_dict

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="PTY assistant is POSIX-only")

_FAKE_SCRIPT = """\
import argparse
import os
import select
import signal
import sys
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--model", default=None)
parser.add_argument("--marker", type=Path, required=True)
args = parser.parse_args()


def write_status(**extra: object) -> None:
    cols, rows = os.get_terminal_size()
    lines = [
        f"pid={os.getpid()}",
        f"model={args.model!s}",
        f"cols={cols}",
        f"rows={rows}",
    ]
    for key, value in extra.items():
        lines.append(f"{key}={value}")
    args.marker.write_text("\\n".join(lines) + "\\n", encoding="utf-8")


def on_winch(signum: int, frame: object) -> None:
    del signum, frame
    cols, rows = os.get_terminal_size()
    print(f"SIZE={cols}x{rows}", flush=True)
    write_status(event="winch")


signal.signal(signal.SIGWINCH, on_winch)
write_status()
print("FAKE_ASSISTANT_READY", flush=True)
if args.model:
    print(f"MODEL={args.model}", flush=True)
else:
    print("MODEL_OMITTED", flush=True)

try:
    while True:
        ready, _, _ = select.select([sys.stdin], [], [], 0.05)
        if not ready:
            continue
        data = os.read(sys.stdin.fileno(), 1024)
        if not data:
            continue
        if b"\\x03" in data:
            print("INTERRUPTED", flush=True)
            write_status(event="interrupt")
            sys.exit(0)
        text = data.decode("utf-8", errors="replace")
        print(f"ECHO:{text}", flush=True)
except KeyboardInterrupt:
    print("INTERRUPTED", flush=True)
    write_status(event="interrupt")
    sys.exit(0)
"""


class _FakeAssistantProfile(CliProfileBase):
    """Minimal profile for the fake assistant adapter used in tests."""

    provider: Literal["fake-asst"] = "fake-asst"


class _FakeNoAutoProfile(CliProfileBase):
    """Profile for a fake adapter without native auto_model."""

    provider: Literal["fake-no-auto"] = "fake-no-auto"


class _FakeMissingProfile(CliProfileBase):
    """Profile for a fake adapter whose executable is never on PATH."""

    provider: Literal["fake-missing"] = "fake-missing"


class _FakeAssistantAdapter(CodingAgentCliAdapter):
    """Interactive fake agent that runs a Python script in a PTY."""

    executable = "python"
    provider = "fake-asst"
    profile_model = _FakeAssistantProfile
    display_name = "Fake Assistant"
    install_url = "https://example.invalid/fake-assistant"
    auto_model: ClassVar[str | None] = "auto"
    script: ClassVar[Path] = Path()
    marker: ClassVar[Path] = Path()

    @override
    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        del request
        return ("--", "unused")

    @override
    def interactive_launch(
        self,
        profile: CliProfileBase,
        *,
        model: str | None,
        prompt: str | None,
        cwd: Path,
    ) -> InteractiveLaunchSpec:
        del profile, prompt
        self.ensure_interactive_model_resolved(model)
        argv: list[str] = [
            sys.executable,
            str(self.script),
            "--marker",
            str(self.marker),
        ]
        if model is not None:
            argv.extend(("--model", model))
        return InteractiveLaunchSpec(argv=tuple(argv), cwd=cwd)


class _FakeNoAutoAdapter(CodingAgentCliAdapter):
    """Fake agent without auto_model; omits ``--model`` when unresolved."""

    executable = "python"
    provider = "fake-no-auto"
    profile_model = _FakeNoAutoProfile
    display_name = "Fake No Auto"
    install_url = "https://example.invalid/fake-no-auto"
    auto_model: ClassVar[str | None] = None
    script: ClassVar[Path] = Path()
    marker: ClassVar[Path] = Path()

    @override
    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        del request
        return ("--", "unused")

    @override
    def interactive_launch(
        self,
        profile: CliProfileBase,
        *,
        model: str | None,
        prompt: str | None,
        cwd: Path,
    ) -> InteractiveLaunchSpec:
        del profile, prompt
        self.ensure_interactive_model_resolved(model)
        argv: list[str] = [
            sys.executable,
            str(self.script),
            "--marker",
            str(self.marker),
        ]
        if model is not None:
            argv.extend(("--model", model))
        return InteractiveLaunchSpec(argv=tuple(argv), cwd=cwd)


class _FakeMissingAdapter(CodingAgentCliAdapter):
    """Fake agent whose interactive argv points at a missing executable."""

    executable = "curupira-missing-assistant-bin"
    provider = "fake-missing"
    profile_model = _FakeMissingProfile
    display_name = "Fake Missing"
    install_url = "https://example.invalid/fake-missing"
    auto_model: ClassVar[str | None] = None

    @override
    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        del request
        return ("--", "unused")

    @override
    def interactive_launch(
        self,
        profile: CliProfileBase,
        *,
        model: str | None,
        prompt: str | None,
        cwd: Path,
    ) -> InteractiveLaunchSpec:
        del profile, prompt
        self.ensure_interactive_model_resolved(model)
        return InteractiveLaunchSpec(argv=(self.executable,), cwd=cwd)


async def _wait_until(predicate: Callable[[], bool], pilot: Any, *, attempts: int = 100) -> None:
    for _ in range(attempts):
        if predicate():
            return
        await pilot.pause(0.05)
    raise AssertionError("condition not met before timeout")


def _child_gone(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return True
    return False


def _marker_fields(marker: Path) -> dict[str, str]:
    lines = marker.read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines if "=" in line)


def _write_fake_script(tmp_path: Path) -> Path:
    script = tmp_path / "fake_assistant_agent.py"
    script.write_text(_FAKE_SCRIPT, encoding="utf-8")
    return script


def _write_config(tmp_path: Path, *, assistant: dict[str, Any] | None = None) -> Path:
    config_path = tmp_path / "settings.toml"
    lines = [
        "[settings]",
        f'state_db_path = "{tmp_path / "state.sqlite3"}"',
        f'workspace_dir = "{tmp_path / "workspaces"}"',
        "max_active_tasks = 10",
        "",
        "[repositories.api]",
        'remote = "https://github.com/acme/api.git"',
        "",
        "[agents.defaults]",
        'profile = "opencode"',
        "",
        "[agents.profiles.opencode]",
        'provider = "opencode"',
        "",
        "[automations.daily]",
        'trigger_type = "cron"',
        'repository = "api"',
        'schedule = "0 9 * * *"',
        'prompt = "Maintain ${repository}"',
        "",
    ]
    if assistant is not None:
        lines.append("[assistant]")
        if "agent" in assistant:
            lines.append(f'agent = "{assistant["agent"]}"')
        if assistant.get("model") is not None:
            lines.append(f'model = "{assistant["model"]}"')
        lines.append("")
    config_path.write_text("\n".join(lines), encoding="utf-8")
    return config_path


def _settings_for(
    tmp_path: Path, *, assistant: dict[str, Any] | None = None
) -> ApplicationSettings:
    return ApplicationSettings.model_validate(
        settings_dict(
            {
                "daily": {
                    "trigger_type": "cron",
                    "repository": "api",
                    "schedule": "0 9 * * *",
                    "prompt": "Maintain ${repository}",
                }
            },
            settings={
                "state_db_path": str(tmp_path / "state.sqlite3"),
                "workspace_dir": str(tmp_path / "workspaces"),
                "max_active_tasks": 10,
            },
            assistant=assistant,
        )
    )


def _install_fake_adapters(
    monkeypatch: pytest.MonkeyPatch,
    adapters: dict[str, type[CodingAgentCliAdapter]],
) -> None:
    import curupira.agents.registry as agent_registry

    agent_registry.registered()
    merged = {**agent_registry._ADAPTERS, **adapters}
    monkeypatch.setattr(agent_registry, "_ADAPTERS", merged)

    def _create(provider: str, runner: object = None) -> CodingAgentCliAdapter:
        del runner
        return agent_registry.get(provider)()

    monkeypatch.setattr("curupira.tui.assistant_launch.create_cli_adapter", _create)


def _build_app(config_path: Path, settings: ApplicationSettings) -> OrchestratorApp:
    app = OrchestratorApp(settings, config_path, NativeGitVersionControl(), TaskTelemetry())

    async def _idle_scheduler() -> None:
        return None

    app._run_scheduler = _idle_scheduler  # type: ignore[method-assign]
    return app


async def _open_assistant_with_pty(
    app: OrchestratorApp, pilot: Any, marker: Path
) -> tuple[AssistantPanel, PtyTerminal]:
    await pilot.press("ctrl+g")
    panel = app.query_one("#assistant-panel", AssistantPanel)
    await _wait_until(lambda: panel.is_open, pilot)
    terminal = app.query_one("#assistant-pty", PtyTerminal)
    await _wait_until(lambda: terminal.pid is not None, pilot)
    await _wait_until(lambda: marker.exists(), pilot)
    return panel, terminal


@pytest.mark.asyncio
async def test_ctrl_g_opens_and_closes_assistant_panel(tmp_path: Path) -> None:
    config_path = _write_config(tmp_path)
    settings = _settings_for(tmp_path)
    app = _build_app(config_path, settings)
    async with app.run_test(size=(120, 40)) as pilot:
        panel = app.query_one("#assistant-panel", AssistantPanel)
        assert not panel.is_open
        await pilot.press("ctrl+g")
        await _wait_until(lambda: panel.is_open, pilot)
        assert panel.has_class("-open")
        assert app.query_one("#assistant-picker", OptionList)
        await pilot.press("ctrl+g")
        await _wait_until(lambda: not panel.is_open, pilot)
        assert not panel.has_class("-open")
        app.exit(0)


@pytest.mark.asyncio
async def test_agent_choice_persists_in_assistant_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _write_fake_script(tmp_path)
    marker = tmp_path / "marker.txt"
    monkeypatch.setattr(_FakeAssistantAdapter, "script", script)
    monkeypatch.setattr(_FakeAssistantAdapter, "marker", marker)
    _install_fake_adapters(monkeypatch, {"fake-asst": _FakeAssistantAdapter})
    config_path = _write_config(tmp_path)
    before = tomllib.loads(config_path.read_text(encoding="utf-8"))
    before_without_assistant = {key: value for key, value in before.items() if key != "assistant"}
    settings = _settings_for(tmp_path)
    app = _build_app(config_path, settings)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("ctrl+g")
        panel = app.query_one("#assistant-panel", AssistantPanel)
        await _wait_until(lambda: panel.is_open, pilot)
        picker = app.query_one("#assistant-picker", OptionList)
        for index, option in enumerate(picker.options):
            if option.id == "fake-asst":
                picker.highlighted = index
                break
        else:
            raise AssertionError("fake-asst not listed in picker")
        await pilot.press("enter")
        await _wait_until(lambda: marker.exists(), pilot)
        after = tomllib.loads(config_path.read_text(encoding="utf-8"))
        after_without_assistant = {key: value for key, value in after.items() if key != "assistant"}
        assert after_without_assistant == before_without_assistant
        assert after["assistant"]["agent"] == "fake-asst"
        assert "model" not in after["assistant"]
        assert app._settings.assistant.agent == "fake-asst"
        await pilot.press("ctrl+g")
        await _wait_until(lambda: not panel.is_open, pilot)
        await pilot.press("ctrl+g")
        await _wait_until(lambda: panel.is_open, pilot)
        assert len(app.query(OptionList)) == 0
        await _wait_until(
            lambda: app.query_one("#assistant-pty", PtyTerminal).pid is not None, pilot
        )
        app.exit(0)


@pytest.mark.asyncio
async def test_adapter_without_auto_model_omits_flag_and_shows_notice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _write_fake_script(tmp_path)
    marker = tmp_path / "marker.txt"
    monkeypatch.setattr(_FakeNoAutoAdapter, "script", script)
    monkeypatch.setattr(_FakeNoAutoAdapter, "marker", marker)
    _install_fake_adapters(monkeypatch, {"fake-no-auto": _FakeNoAutoAdapter})
    config_path = _write_config(tmp_path, assistant={"agent": "fake-no-auto"})
    settings = _settings_for(tmp_path, assistant={"agent": "fake-no-auto"})
    app = _build_app(config_path, settings)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("ctrl+g")
        panel = app.query_one("#assistant-panel", AssistantPanel)
        await _wait_until(lambda: panel.is_open, pilot)
        assert "no native automatic model" in panel.notice_text
        await _wait_until(lambda: marker.exists(), pilot)
        content = marker.read_text(encoding="utf-8")
        assert "model=None" in content
        assert app.query_one("#assistant-pty", PtyTerminal).pid is not None
        app.exit(0)


@pytest.mark.asyncio
async def test_missing_binary_shows_clear_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_adapters(monkeypatch, {"fake-missing": _FakeMissingAdapter})
    config_path = _write_config(tmp_path, assistant={"agent": "fake-missing"})
    settings = _settings_for(tmp_path, assistant={"agent": "fake-missing"})
    app = _build_app(config_path, settings)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("ctrl+g")
        panel = app.query_one("#assistant-panel", AssistantPanel)
        await _wait_until(lambda: panel.is_open, pilot)
        assert "was not found on PATH" in panel.message_text
        assert "curupira-missing-assistant-bin" in panel.message_text
        assert len(app.query(PtyTerminal)) == 0
        app.exit(0)


@pytest.mark.asyncio
async def test_escape_closes_panel_on_error_screen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_fake_adapters(monkeypatch, {"fake-missing": _FakeMissingAdapter})
    config_path = _write_config(tmp_path, assistant={"agent": "fake-missing"})
    settings = _settings_for(tmp_path, assistant={"agent": "fake-missing"})
    app = _build_app(config_path, settings)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("ctrl+g")
        panel = app.query_one("#assistant-panel", AssistantPanel)
        await _wait_until(lambda: panel.is_open, pilot)
        await _wait_until(lambda: panel.has_focus, pilot)
        await pilot.press("escape")
        await _wait_until(lambda: not panel.is_open, pilot)
        app.exit(0)


@pytest.mark.asyncio
async def test_closing_panel_terminates_child_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _write_fake_script(tmp_path)
    marker = tmp_path / "marker.txt"
    monkeypatch.setattr(_FakeAssistantAdapter, "script", script)
    monkeypatch.setattr(_FakeAssistantAdapter, "marker", marker)
    _install_fake_adapters(monkeypatch, {"fake-asst": _FakeAssistantAdapter})
    config_path = _write_config(tmp_path, assistant={"agent": "fake-asst"})
    settings = _settings_for(tmp_path, assistant={"agent": "fake-asst"})
    app = _build_app(config_path, settings)
    async with app.run_test(size=(120, 40)) as pilot:
        panel, terminal = await _open_assistant_with_pty(app, pilot, marker)
        child_pid = terminal.pid
        assert child_pid is not None
        await pilot.press("ctrl+g")
        await _wait_until(lambda: not panel.is_open, pilot)
        await _wait_until(lambda: _child_gone(child_pid), pilot, attempts=80)
        app.exit(0)


@pytest.mark.asyncio
async def test_f6_toggles_focus_between_panel_and_main_tui(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _write_fake_script(tmp_path)
    marker = tmp_path / "marker.txt"
    monkeypatch.setattr(_FakeAssistantAdapter, "script", script)
    monkeypatch.setattr(_FakeAssistantAdapter, "marker", marker)
    _install_fake_adapters(monkeypatch, {"fake-asst": _FakeAssistantAdapter})
    config_path = _write_config(tmp_path, assistant={"agent": "fake-asst"})
    settings = _settings_for(tmp_path, assistant={"agent": "fake-asst"})
    app = _build_app(config_path, settings)
    async with app.run_test(size=(120, 40)) as pilot:
        panel, terminal = await _open_assistant_with_pty(app, pilot, marker)
        await _wait_until(lambda: terminal.has_focus, pilot)

        # With PTY focused, F1 is swallowed (no Help screen).
        await pilot.press("f1")
        await pilot.pause(0.05)
        assert not any(isinstance(screen, HelpScreen) for screen in app.screen_stack)

        await pilot.press("f6")
        log = app.query_one("#orchestrator-log", RichLog)
        await _wait_until(lambda: log.has_focus, pilot)
        assert panel.is_open
        assert not terminal.has_focus

        await pilot.press("f1")
        await _wait_until(
            lambda: any(isinstance(screen, HelpScreen) for screen in app.screen_stack),
            pilot,
        )
        await pilot.press("escape")
        await _wait_until(
            lambda: not any(isinstance(screen, HelpScreen) for screen in app.screen_stack),
            pilot,
        )

        await pilot.press("f6")
        await _wait_until(lambda: terminal.has_focus, pilot)
        # Distinctive glyph so local PTY echo proves keys reach the child again.
        await pilot.press("z")
        await _wait_until(lambda: "z" in str(terminal.render()), pilot)
        app.exit(0)


@pytest.mark.asyncio
async def test_resize_propagates_to_assistant_pty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _write_fake_script(tmp_path)
    marker = tmp_path / "marker.txt"
    monkeypatch.setattr(_FakeAssistantAdapter, "script", script)
    monkeypatch.setattr(_FakeAssistantAdapter, "marker", marker)
    _install_fake_adapters(monkeypatch, {"fake-asst": _FakeAssistantAdapter})
    config_path = _write_config(tmp_path, assistant={"agent": "fake-asst"})
    settings = _settings_for(tmp_path, assistant={"agent": "fake-asst"})
    app = _build_app(config_path, settings)
    async with app.run_test(size=(120, 40)) as pilot:
        panel, _terminal = await _open_assistant_with_pty(app, pilot, marker)
        initial = _marker_fields(marker)
        initial_cols = int(initial["cols"])
        dashboard = app.query_one("#dashboard")
        assert panel.content_size.width >= 40
        assert abs(panel.content_size.width - dashboard.content_size.width) <= 4

        await pilot.resize_terminal(160, 50)
        await _wait_until(
            lambda: (
                marker.exists() and int(_marker_fields(marker).get("cols", "0")) != initial_cols
            ),
            pilot,
            attempts=120,
        )
        resized = _marker_fields(marker)
        assert int(resized["cols"]) > initial_cols
        assert panel.is_open
        assert abs(panel.content_size.width - dashboard.content_size.width) <= 4
        app.exit(0)


def _wait_child_gone(pid: int, *, timeout: float = 4.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline and not _child_gone(pid):
        time.sleep(0.05)
    assert _child_gone(pid)


@pytest.mark.asyncio
async def test_app_exit_with_panel_open_terminates_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _write_fake_script(tmp_path)
    marker = tmp_path / "marker.txt"
    monkeypatch.setattr(_FakeAssistantAdapter, "script", script)
    monkeypatch.setattr(_FakeAssistantAdapter, "marker", marker)
    _install_fake_adapters(monkeypatch, {"fake-asst": _FakeAssistantAdapter})
    config_path = _write_config(tmp_path, assistant={"agent": "fake-asst"})
    settings = _settings_for(tmp_path, assistant={"agent": "fake-asst"})
    app = _build_app(config_path, settings)
    child_pid: int | None = None
    async with app.run_test(size=(120, 40)) as pilot:
        _panel, terminal = await _open_assistant_with_pty(app, pilot, marker)
        child_pid = terminal.pid
        assert child_pid is not None
        # Exit without closing the panel first; unmount must reap the child.
        app.exit(0)
    assert child_pid is not None
    _wait_child_gone(child_pid)


@pytest.mark.asyncio
async def test_ctrl_c_on_main_tui_quits_and_terminates_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _write_fake_script(tmp_path)
    marker = tmp_path / "marker.txt"
    monkeypatch.setattr(_FakeAssistantAdapter, "script", script)
    monkeypatch.setattr(_FakeAssistantAdapter, "marker", marker)
    _install_fake_adapters(monkeypatch, {"fake-asst": _FakeAssistantAdapter})
    config_path = _write_config(tmp_path, assistant={"agent": "fake-asst"})
    settings = _settings_for(tmp_path, assistant={"agent": "fake-asst"})
    app = _build_app(config_path, settings)
    child_pid: int | None = None
    async with app.run_test(size=(120, 40)) as pilot:
        _panel, terminal = await _open_assistant_with_pty(app, pilot, marker)
        child_pid = terminal.pid
        assert child_pid is not None
        await pilot.press("f6")
        await _wait_until(lambda: app.query_one("#orchestrator-log", RichLog).has_focus, pilot)
        await pilot.press("ctrl+c")
        await _wait_until(lambda: app.return_value is not None or not app.is_running, pilot)
    assert child_pid is not None
    _wait_child_gone(child_pid)


@pytest.mark.asyncio
async def test_ctrl_c_with_pty_focused_interrupts_agent_not_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _write_fake_script(tmp_path)
    marker = tmp_path / "marker.txt"
    monkeypatch.setattr(_FakeAssistantAdapter, "script", script)
    monkeypatch.setattr(_FakeAssistantAdapter, "marker", marker)
    _install_fake_adapters(monkeypatch, {"fake-asst": _FakeAssistantAdapter})
    config_path = _write_config(tmp_path, assistant={"agent": "fake-asst"})
    settings = _settings_for(tmp_path, assistant={"agent": "fake-asst"})
    app = _build_app(config_path, settings)
    async with app.run_test(size=(120, 40)) as pilot:
        panel, terminal = await _open_assistant_with_pty(app, pilot, marker)
        await _wait_until(lambda: terminal.has_focus, pilot)
        await pilot.press("ctrl+c")
        await _wait_until(
            lambda: marker.exists() and _marker_fields(marker).get("event") == "interrupt",
            pilot,
            attempts=120,
        )
        assert panel.is_open
        assert app.is_running
        assert app.return_value is None
        app.exit(0)


@pytest.mark.asyncio
async def test_persist_missing_config_shows_message_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _write_fake_script(tmp_path)
    marker = tmp_path / "marker.txt"
    monkeypatch.setattr(_FakeAssistantAdapter, "script", script)
    monkeypatch.setattr(_FakeAssistantAdapter, "marker", marker)
    _install_fake_adapters(monkeypatch, {"fake-asst": _FakeAssistantAdapter})
    config_path = _write_config(tmp_path)
    settings = _settings_for(tmp_path)
    app = _build_app(config_path, settings)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("ctrl+g")
        panel = app.query_one("#assistant-panel", AssistantPanel)
        await _wait_until(lambda: panel.is_open, pilot)
        config_path.unlink()
        picker = app.query_one("#assistant-picker", OptionList)
        for index, option in enumerate(picker.options):
            if option.id == "fake-asst":
                picker.highlighted = index
                break
        await pilot.press("enter")
        await _wait_until(lambda: "Could not save assistant.agent" in panel.message_text, pilot)
        assert app._settings.assistant.agent == "fake-asst"
        await _wait_until(lambda: marker.exists(), pilot)
        assert app.is_running
        app.exit(0)


@pytest.mark.asyncio
async def test_persist_readonly_config_shows_message_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _write_fake_script(tmp_path)
    marker = tmp_path / "marker.txt"
    monkeypatch.setattr(_FakeAssistantAdapter, "script", script)
    monkeypatch.setattr(_FakeAssistantAdapter, "marker", marker)
    _install_fake_adapters(monkeypatch, {"fake-asst": _FakeAssistantAdapter})

    # Atomic replace only needs directory write permission, so simulate a
    # PermissionError from the writer instead of chmod on the file alone.
    def _deny_persist(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("Read-only file system")

    monkeypatch.setattr(
        "curupira.tui.assistant_panel.persist_assistant_agent",
        _deny_persist,
    )
    config_path = _write_config(tmp_path)
    settings = _settings_for(tmp_path)
    app = _build_app(config_path, settings)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("ctrl+g")
        panel = app.query_one("#assistant-panel", AssistantPanel)
        await _wait_until(lambda: panel.is_open, pilot)
        picker = app.query_one("#assistant-picker", OptionList)
        for index, option in enumerate(picker.options):
            if option.id == "fake-asst":
                picker.highlighted = index
                break
        await pilot.press("enter")
        await _wait_until(lambda: "Could not save assistant.agent" in panel.message_text, pilot)
        assert "Read-only file system" in panel.message_text
        assert app._settings.assistant.agent == "fake-asst"
        await _wait_until(lambda: marker.exists(), pilot)
        assert app.is_running
        app.exit(0)


@pytest.mark.asyncio
async def test_persist_unsupported_inline_shape_shows_message_without_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _write_fake_script(tmp_path)
    marker = tmp_path / "marker.txt"
    monkeypatch.setattr(_FakeAssistantAdapter, "script", script)
    monkeypatch.setattr(_FakeAssistantAdapter, "marker", marker)
    _install_fake_adapters(monkeypatch, {"fake-asst": _FakeAssistantAdapter})
    config_path = _write_config(tmp_path)
    # Prepend an inline assistant table so surgical rewrite would duplicate the key.
    original = 'assistant = {model = "x"}\n' + config_path.read_text(encoding="utf-8")
    config_path.write_text(original, encoding="utf-8")
    settings = _settings_for(tmp_path)
    app = _build_app(config_path, settings)
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("ctrl+g")
        panel = app.query_one("#assistant-panel", AssistantPanel)
        await _wait_until(lambda: panel.is_open, pilot)
        picker = app.query_one("#assistant-picker", OptionList)
        for index, option in enumerate(picker.options):
            if option.id == "fake-asst":
                picker.highlighted = index
                break
        await pilot.press("enter")
        await _wait_until(lambda: "unsupported TOML shape" in panel.message_text, pilot)
        assert config_path.read_text(encoding="utf-8") == original
        assert app._settings.assistant.agent == "fake-asst"
        await _wait_until(lambda: marker.exists(), pilot)
        assert app.is_running
        app.exit(0)
