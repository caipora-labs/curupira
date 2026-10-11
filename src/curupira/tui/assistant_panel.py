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
from curupira.tui.assistant_persist import persist_assistant_agent
from curupira.tui.pty_terminal import PtyTerminal


class AssistantPanel(Vertical):
    """Half-width side panel that hosts agent selection or an interactive PTY.

    Ctrl+G on the host app toggles visibility. When open without a stored
    ``assistant.agent``, the panel lists registered coding-agent providers.
    Choosing one writes ``[assistant]`` in the existing settings TOML and starts
    the adapter's interactive launch inside :class:`PtyTerminal`.
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

    @property
    def is_open(self) -> bool:
        """Whether the side panel is currently visible."""
        return self._open

    def update_settings(self, settings: ApplicationSettings) -> None:
        """Replace the in-memory settings snapshot (for example after reload)."""
        self._settings = settings

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
        try:
            self.query_one("#assistant-pty", PtyTerminal).focus()
            return
        except NoMatches:
            pass
        try:
            self.query_one("#assistant-picker", OptionList).focus()
            return
        except NoMatches:
            pass
        self.focus()

    async def action_close_panel(self) -> None:
        """Binding handler: close the panel."""
        await self.close_panel()

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Persist the chosen provider and start (or explain) the interactive session."""
        option_id = event.option_id
        if not isinstance(option_id, str):
            return
        self._persist_and_apply(option_id)
        await self._clear_body()
        self._mount_body()
        self.focus_content()

    async def on_pty_terminal_focus_released(self, message: PtyTerminal.FocusReleased) -> None:
        """Ctrl+G inside the PTY closes the panel (escape key on PtyTerminal)."""
        del message
        await self.close_panel()

    def _persist_and_apply(self, provider: str) -> None:
        """Write ``assistant.agent`` and update the in-memory settings snapshot."""
        adapters = registered()
        if provider not in adapters:
            self._set_message(f"Unknown coding-agent provider: {provider}")
            return
        model = self._settings.assistant.model
        try:
            resolve_assistant_model(adapters[provider], model)
        except ValueError:
            model = None
        persist_assistant_agent(self._config_path, agent=provider, model=model)
        assistant = AssistantSettings(agent=provider, model=model)
        self._settings = self._settings.model_copy(update={"assistant": assistant})
        self.post_message(self.AgentChosen(provider, self._settings))

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
            return
        notes = "\n".join(plan.spec.notes)
        if notes:
            existing = self.query_one("#assistant-notice", Static)
            prior = str(existing.renderable) if existing.renderable else ""
            combined = "\n".join(part for part in (prior, notes) if part)
            self._set_notice(combined)
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
        self.query_one("#assistant-notice", Static).update(text)

    def _set_message(self, text: str) -> None:
        """Update the main status / error message."""
        self.query_one("#assistant-message", Static).update(text)
