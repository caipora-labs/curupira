"""MkDocs macros for rendering versioned documentation data."""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Protocol


class MacroEnvironment(Protocol):
    """Interface provided by the MkDocs macros plugin."""

    def macro(self, function: Callable[[], str]) -> Callable[[], str]:
        """Register a zero-argument string-producing macro."""


_TRIGGER_ROWS: tuple[tuple[str, str, str, str], ...] = (
    (
        "github_issues",
        "github.md",
        "`gh` authenticated (`gh auth login`)",
        "Finds issues using filters you set in TOML",
    ),
    (
        "github_pull_requests",
        "github.md",
        "`gh` authenticated (`gh auth login`)",
        "Finds pull requests using filters you set in TOML",
    ),
    (
        "azure_cli_pull_requests",
        "#azure-devops-pull-requests",
        "`az` + Azure DevOps extension (`az login`)",
        "Lists Azure DevOps pull requests with the Azure CLI",
    ),
    (
        "trello_cli_cards",
        "trello.md",
        "`trello` CLI (`trello auth login`)",
        "Finds open cards on a Trello board",
    ),
    (
        "monday_items",
        "monday.md",
        "`MONDAY_API_TOKEN` (or `token_env`) set",
        "Finds board items through monday.com's API (read-only)",
    ),
    (
        "cron",
        "#cron",
        "None (local schedule)",
        "Runs on a local schedule you set (built into the Rust CLI)",
    ),
)

_AGENT_ROWS: tuple[tuple[str, str, str], ...] = (
    ("claude", "claude", "providers/claude.md"),
    ("codex", "codex", "providers/codex.md"),
    ("cursor", "agent", "providers/cursor.md"),
    ("gemini", "gemini", "providers/gemini.md"),
    ("copilot", "copilot", "providers/copilot.md"),
    ("kilo", "kilo", "providers/kilo.md"),
    ("opencode", "opencode", "providers/opencode.md"),
    ("pi", "pi", "providers/pi.md"),
    ("qwen", "qwen", "providers/qwen.md"),
)


def define_env(env: MacroEnvironment) -> None:
    """Register macros used by the English docs."""

    @env.macro
    def project_version() -> str:
        data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
        return str(data["project"]["version"])

    @env.macro
    def triggers_table() -> str:
        lines = [
            "| Trigger | Guide | Prerequisites | Summary |",
            "| --- | --- | --- | --- |",
        ]
        for trigger, guide, prereq, summary in _TRIGGER_ROWS:
            lines.append(f"| `{trigger}` | [{guide}]({guide}) | {prereq} | {summary} |")
        return "\n".join(lines)

    @env.macro
    def agents_table() -> str:
        lines = [
            "| Provider | Executable | Guide |",
            "| --- | --- | --- |",
        ]
        for provider, executable, guide in _AGENT_ROWS:
            lines.append(f"| `{provider}` | `{executable}` | [{guide}]({guide}) |")
        return "\n".join(lines)
