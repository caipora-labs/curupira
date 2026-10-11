"""Embedded side-panel coding-agent assistant for the orchestrator TUI."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.message import Message
from textual.widgets import Label, OptionList, Static
from textual.widgets.option_list import Option
from typing_extensions import override

from curupira.agents.assistant import resolve_assistant_model
from curupira.agents.registry import registered
from curupira.config import ApplicationSettings
from curupira.models import AssistantSettings
from curupira.tui.assistant_launch import (
    list_assistant_providers,
    plan_assistant_launch,
    pty_environment_for,
)
from curupira.tui.assistant_persist import (
    UnsupportedAssistantTomlError,
    persist_assistant_agent,
)
from curupira.tui.pty_terminal import PtyTerminal


class AssistantPanel(Vertical, can_focus=True):
    """Half-width side panel that hosts agent selection or an interactive PTY.

    Ctrl+G on the host app toggles visibility. When open without a stored
    ``assistant.agent``, the panel lists registered coding-agent providers.
    Choosing one writes ``[assistant]`` in the existing settings TOML and starts
    the adapter's interactive launch inside :class:`PtyTerminal`. The panel itself
    is focusable so Escape closes it on error screens (no PTY); with a PTY focused,
    Escape is forwarded to the agent instead.
    """

    DEFAULT_CSS = """
    AssistantPanel {
        width: 1fr;
        height: 1fr;
        border-left: solid #c8c8c8;
        background: #0a0a0a;
        display: none;
        padding: 0 1;
    }
    AssistantPanel.-open {
        display: block;
    }
    AssistantPanel #assistant-title {
        text-style: bold;
        color: #f0f0f0;
        height: 1;
        margin: 1 0;
    }
    AssistantPanel #assistant-notice {
        color: #ffb86c;
        height: auto;
        margin-bottom: 1;
    }
    AssistantPanel #assistant-message {
        color: #e8e8e8;
        height: auto;
        margin: 1 0;
    }
    AssistantPanel #assistant-picker {
        height: 1fr;
        border: solid #404040;
    }
    AssistantPanel #assistant-pty {
        height: 1fr;
        min-height: 5;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "close_panel", "Fechar", show=False),
    ]

    class AgentChosen(Message):
        """Posted after the user picks a provider and it is persisted.

        Attributes:
            provider: Registered coding-agent provider name.
            settings: Updated in-memory application settings.
        """

        def __init__(self, provider: str, settings: ApplicationSettings) -> None:
            super().__init__()
            self.provider = provider
            self.settings = settings

    class Closed(Message):
        """Posted when the panel finishes closing and tearing down its child."""

    def __init__(
        self,
        settings: ApplicationSettings,
        config_path: Path,
        *,
        cwd: Path | None = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Create the assistant panel.

        Args:
            settings: Loaded application settings (``assistant`` may be unset).
            config_path: TOML path used to persist ``assistant.agent``.
            cwd: Working directory for the interactive session; defaults to
                :func:`Path.cwd`.
            name: Optional Textual widget name.
            id: Optional Textual widget id.
            classes: Optional Textual CSS classes.
        """
        super().__init__(name=name, id=id, classes=classes)
        self._settings = settings
        self._config_path = config_path
        self._cwd = cwd if cwd is not None else Path.cwd()
        self._open = False
        self._notice_text = ""
        self._message_text = ""

    @property
    def is_open(self) -> bool:
        """Whether the side panel is currently visible."""
        return self._open

    @property
    def notice_text(self) -> str:
        """Current amber notice text (model/default caveats), not read from the widget."""
        return self._notice_text

    @property
    def message_text(self) -> str:
        """Current status / error message text."""
        return self._message_text

    def update_settings(self, settings: ApplicationSettings) -> None:
        """Replace the in-memory settings snapshot (for example after reload)."""
        self._settings = settings

    def focus_is_inside(self) -> bool:
        """Return whether the screen's focused widget is this panel or a descendant."""
        focused = self.app.focused
        if focused is None:
            return False
        return focused is self or self in focused.ancestors

    def pty_terminal(self) -> PtyTerminal | None:
        """Return the mounted PTY widget, or ``None`` when absent."""
        try:
            return self.query_one("#assistant-pty", PtyTerminal)
        except NoMatches:
            return None

    @override
    def compose(self) -> ComposeResult:
        """Render the title; body widgets are mounted when the panel opens."""
        yield Label("ASSISTENTE", id="assistant-title")
        yield Static("", id="assistant-notice")
        yield Static("", id="assistant-message")

    def open_panel(self) -> None:
        """Show the panel and mount selection UI or the interactive PTY."""
        if self._open:
            self.focus_content()
            return
        self._open = True
        self.add_class("-open")
        self._mount_body()
        self.focus_content()

    async def close_panel(self) -> None:
        """Hide the panel and tear down any PTY child via widget unmount."""
        if not self._open:
            return
        self._open = False
        self.remove_class("-open")
        await self._clear_body()
        self.post_message(self.Closed())

    async def toggle(self) -> None:
        """Open the panel when closed; close it when open."""
        if self._open:
            await self.close_panel()
        else:
            self.open_panel()

    def focus_content(self) -> None:
        """Move keyboard focus to the picker or PTY inside the panel."""
        self.can_focus = True
        try:
            terminal = self.query_one("#assistant-pty", PtyTerminal)
            terminal.can_focus = True
            terminal.focus()
            return
        except NoMatches:
            pass
        try:
            picker = self.query_one("#assistant-picker", OptionList)
            picker.can_focus = True
            picker.focus()
            return
        except NoMatches:
            pass
        self.focus()

    def suspend_focus_for_host(self) -> None:
        """Drop panel widgets from the Tab cycle so F6 returns keys to the dashboard.

        After F6 moves focus to the main TUI, Tab must cycle dashboard controls (and
        F1–F5 stay on the host). Leaving the PTY/picker focusable would steal Tab.
        """
        terminal = self.pty_terminal()
        if terminal is not None:
            terminal.can_focus = False
        try:
            self.query_one("#assistant-picker", OptionList).can_focus = False
        except NoMatches:
            pass
        self.can_focus = False

    async def action_close_panel(self) -> None:
        """Close the panel, or forward Escape to a focused assistant PTY.

        The panel binds Escape for picker/error screens. When the PTY has focus that
        binding would otherwise swallow the key before ``PtyTerminal.on_key``; forward
        ``\\x1b`` to the child and keep the panel open instead.
        """
        terminal = self.pty_terminal()
        if terminal is not None and terminal.has_focus:
            terminal.write(b"\x1b")
            return
        await self.close_panel()

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Persist the chosen provider and start (or explain) the interactive session."""
        option_id = event.option_id
        if not isinstance(option_id, str):
            return
        persist_error = self._persist_and_apply(option_id)
        await self._clear_body()
        self._mount_body()
        if persist_error is not None:
            self._set_message(persist_error)
        self.focus_content()

    async def on_pty_terminal_focus_released(self, message: PtyTerminal.FocusReleased) -> None:
        """Ctrl+G inside the PTY closes the panel (escape key on PtyTerminal)."""
        del message
        await self.close_panel()

    def _persist_and_apply(self, provider: str) -> str | None:
        """Write ``assistant.agent`` and update the in-memory settings snapshot.

        Returns a user-facing error when the disk write fails. The in-memory choice
        still applies so the interactive session can start.
        """
        adapters = registered()
        if provider not in adapters:
            self._set_message(f"Unknown coding-agent provider: {provider}")
            return None
        model = self._settings.assistant.model
        try:
            resolve_assistant_model(adapters[provider], model)
        except ValueError:
            model = None
        persist_error: str | None = None
        try:
            persist_assistant_agent(self._config_path, agent=provider, model=model)
        except UnsupportedAssistantTomlError as error:
            persist_error = str(error)
        except OSError as error:
            persist_error = f"Could not save assistant.agent to {self._config_path}: {error}"
        assistant = AssistantSettings(agent=provider, model=model)
        self._settings = self._settings.model_copy(update={"assistant": assistant})
        self.post_message(self.AgentChosen(provider, self._settings))
        return persist_error

    def _mount_body(self) -> None:
        """Mount picker, error text, or PtyTerminal based on current settings."""
        self._set_notice("")
        self._set_message("")
        plan = plan_assistant_launch(self._settings, cwd=self._cwd)
        if plan is None:
            self._mount_picker()
            return
        if plan.notice:
            self._set_notice(plan.notice)
        if plan.error is not None or plan.spec is None:
            self._set_message(plan.error or "Interactive launch is unavailable.")
            self.focus()
            return
        notes = "\n".join(plan.spec.notes)
        if notes:
            self._append_notice(notes)
        terminal = PtyTerminal(
            plan.spec.argv,
            env=pty_environment_for(plan.spec),
            cwd=plan.spec.cwd,
            escape_key="ctrl+g",
            id="assistant-pty",
        )
        self.mount(terminal)

    def _mount_picker(self) -> None:
        """Ask which registered coding agent should power the assistant."""
        self._set_message("Choose a coding agent for the assistant:")
        options = [
            Option(f"{display_name}  ({provider})", id=provider)
            for provider, display_name in list_assistant_providers()
        ]
        picker = OptionList(*options, id="assistant-picker")
        self.mount(picker)

    async def _clear_body(self) -> None:
        """Remove picker / PTY children so PtyTerminal unmount reaps the child."""
        for child in list(self.children):
            if child.id in {"assistant-title", "assistant-notice", "assistant-message"}:
                continue
            await child.remove()

    def _set_notice(self, text: str) -> None:
        """Update the amber notice line above the PTY."""
        self._notice_text = text
        self.query_one("#assistant-notice", Static).update(text)

    def _append_notice(self, text: str) -> None:
        """Append a line to the notice using stored state (not the Static renderable)."""
        if not text:
            return
        combined = "\n".join(part for part in (self._notice_text, text) if part)
        self._set_notice(combined)

    def _set_message(self, text: str) -> None:
        """Update the main status / error message."""
        self._message_text = text
        self.query_one("#assistant-message", Static).update(text)
