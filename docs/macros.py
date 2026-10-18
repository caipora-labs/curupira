"""MkDocs macros for rendering documentation tables from the project data."""

from __future__ import annotations

import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Protocol


class MacroEnvironment(Protocol):
    """Interface provided by the MkDocs macros plugin."""

    def macro(self, function: Callable[[], str]) -> Callable[[], str]:
        """Register a zero-argument string-producing macro."""


# (trigger, guide page, {language: (prerequisites, summary)}); English is the fallback.
_TRIGGER_ROWS: tuple[tuple[str, str, dict[str, tuple[str, str]]], ...] = (
    (
        "plugins-py/github-issues",
        "github.md",
        {
            "en": (
                "`gh` authenticated (`gh auth login`)",
                "Finds issues using filters you set in TOML",
            ),
            "pt": (
                "`gh` autenticado (`gh auth login`)",
                "Encontra issues usando filtros definidos no TOML",
            ),
            "es": (
                "`gh` autenticado (`gh auth login`)",
                "Encuentra issues usando filtros definidos en el TOML",
            ),
        },
    ),
    (
        "plugins-py/github-pull-requests",
        "github.md",
        {
            "en": (
                "`gh` authenticated (`gh auth login`)",
                "Finds pull requests using filters you set in TOML",
            ),
            "pt": (
                "`gh` autenticado (`gh auth login`)",
                "Encontra pull requests usando filtros definidos no TOML",
            ),
            "es": (
                "`gh` autenticado (`gh auth login`)",
                "Encuentra pull requests usando filtros definidos en el TOML",
            ),
        },
    ),
    (
        "plugins-py/github-project-items",
        "github-projects.md",
        {
            "en": (
                "`gh` authenticated with the `read:project` scope",
                "Finds issues and pull requests sitting in a GitHub Project board column",
            ),
            "pt": (
                "`gh` autenticado com o escopo `read:project`",
                "Encontra issues e pull requests em uma coluna de um board do GitHub Projects",
            ),
            "es": (
                "`gh` autenticado con el alcance `read:project`",
                "Encuentra issues y pull requests en una columna de un tablero de GitHub Projects",
            ),
        },
    ),
    (
        "cron",
        "automations.md#cron",
        {
            "en": (
                "None (local schedule)",
                "Runs on a local schedule you set (built into the Rust CLI)",
            ),
            "pt": (
                "Nenhum (agenda local)",
                "Roda em uma agenda local definida por você (embutido na CLI Rust)",
            ),
            "es": (
                "Ninguno (agenda local)",
                "Se ejecuta en una agenda local que defines (integrado en la CLI Rust)",
            ),
        },
    ),
)

_TRIGGER_HEADERS: dict[str, tuple[str, str, str, str]] = {
    "en": ("Trigger", "Guide", "Prerequisites", "Summary"),
    "pt": ("Trigger", "Guia", "Pré-requisitos", "Resumo"),
    "es": ("Trigger", "Guía", "Requisitos previos", "Resumen"),
}

_AGENT_HEADERS: dict[str, tuple[str, str, str]] = {
    "en": ("Provider", "Executable", "Guide"),
    "pt": ("Provider", "Executável", "Guia"),
    "es": ("Proveedor", "Ejecutable", "Guía"),
}

_REQUIREMENT_TEXT: dict[str, tuple[str, str]] = {
    # (Python line, prefix of optional tools)
    "en": ("Python {range} on {platforms}.", "Optional, "),
    "pt": ("Python {range} em {platforms}.", "Opcional, "),
    "es": ("Python {range} en {platforms}.", "Opcional, "),
}

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


_REQUIREMENTS = tomllib.loads(
    (Path(__file__).parent / "data" / "requirements.toml").read_text(encoding="utf-8")
)


def _lang(lang: str) -> str:
    return lang if lang in _TRIGGER_HEADERS else "en"


def _localized(table: dict[str, object], key: str, lang: str) -> object:
    """Return `<key>_<lang>` when the data defines it, otherwise the English `<key>`."""
    return table.get(f"{key}_{lang}", table[key]) if lang != "en" else table[key]


def define_env(env: MacroEnvironment) -> None:
    """Register macros used by the documentation; each takes an optional language code."""

    @env.macro
    def requirements_list(lang: str = "en") -> str:
        lang = _lang(lang)
        python = _REQUIREMENTS["python"]
        line, optional = _REQUIREMENT_TEXT[lang]
        platforms = _localized(python, "platforms", lang)
        lines = [f"- {line.format(range=python['range'], platforms=platforms)}"]
        for tool in _REQUIREMENTS["required_tools"]:
            detail = _localized(tool, "detail", lang)
            lines.append(f"- [{tool['name']}]({tool['url']}): {detail}")
        for tool in _REQUIREMENTS["optional_tools"]:
            detail = _localized(tool, "detail", lang)
            lines.append(f"- {optional}[{tool['name']}]({tool['url']}): {detail}")
        return "\n".join(lines)

    @env.macro
    def triggers_table(lang: str = "en") -> str:
        lang = _lang(lang)
        header = _TRIGGER_HEADERS[lang]
        lines = [
            "| " + " | ".join(header) + " |",
            "| --- | --- | --- | --- |",
        ]
        for trigger, guide, texts in _TRIGGER_ROWS:
            prereq, summary = texts[lang]
            lines.append(f"| `{trigger}` | [{guide}]({guide}) | {prereq} | {summary} |")
        return "\n".join(lines)

    @env.macro
    def agents_table(lang: str = "en") -> str:
        lang = _lang(lang)
        header = _AGENT_HEADERS[lang]
        lines = [
            "| " + " | ".join(header) + " |",
            "| --- | --- | --- |",
        ]
        for provider, executable, guide in _AGENT_ROWS:
            lines.append(f"| `{provider}` | `{executable}` | [{guide}]({guide}) |")
        return "\n".join(lines)
