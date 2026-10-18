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

_TRIGGER_HEADERS: dict[str, tuple[str, str, str]] = {
    "en": ("Trigger", "Prerequisites", "Summary"),
    "pt": ("Trigger", "Pré-requisitos", "Resumo"),
    "es": ("Trigger", "Requisitos previos", "Resumen"),
}

_AGENT_HEADERS: dict[str, tuple[str, str, str, str, str]] = {
    "en": ("Agent", "`provider`", "Command", "`agent` option", "`effort` option"),
    "pt": ("Agente", "`provider`", "Comando", "Opção `agent`", "Opção `effort`"),
    "es": ("Agente", "`provider`", "Comando", "Opción `agent`", "Opción `effort`"),
}

_REQUIREMENT_TEXT: dict[str, tuple[str, str, str]] = {
    # (Python line, Node.js line, prefix of optional tools)
    "en": (
        (
            "Python {range} on {platforms}, only for the PyPI install and for extensions launched "
            "with `uvx`."
        ),
        (
            "Node.js {range}, only for the npm install (`@caipora/curupira`) and for extensions "
            "launched with `npx`."
        ),
        "Optional, ",
    ),
    "pt": (
        (
            "Python {range} em {platforms}, apenas para a instalação pelo PyPI e para extensões "
            "iniciadas com `uvx`."
        ),
        (
            "Node.js {range}, apenas para a instalação pelo npm (`@caipora/curupira`) e para "
            "extensões iniciadas com `npx`."
        ),
        "Opcional, ",
    ),
    "es": (
        (
            "Python {range} en {platforms}, solo para la instalación desde PyPI y para extensiones "
            "iniciadas con `uvx`."
        ),
        (
            "Node.js {range}, solo para la instalación desde npm (`@caipora/curupira`) y para "
            "extensiones iniciadas con `npx`."
        ),
        "Opcional, ",
    ),
}

# (name, provider, executable, guide, native flag for `agent`, native flag for `effort`).
_AGENT_ROWS: tuple[tuple[str, str, str, str, str | None, str | None], ...] = (
    ("Claude Code", "claude", "claude", "providers/claude.md", "--agent", "--effort"),
    ("Codex", "codex", "codex", "providers/codex.md", "--profile", "model_reasoning_effort"),
    ("Cursor", "cursor", "agent", "providers/cursor.md", "--mode", None),
    ("Gemini CLI", "gemini", "gemini", "providers/gemini.md", None, None),
    (
        "GitHub Copilot CLI",
        "copilot",
        "copilot",
        "providers/copilot.md",
        "--agent",
        "--reasoning-effort",
    ),
    ("Kilo CLI", "kilo", "kilo", "providers/kilo.md", "--agent", "--variant"),
    ("OpenCode", "opencode", "opencode", "providers/opencode.md", "--agent", "--variant"),
    ("pi", "pi", "pi", "providers/pi.md", None, "--thinking"),
    ("Qwen Code", "qwen", "qwen", "providers/qwen.md", None, None),
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
        node = _REQUIREMENTS["node"]
        python_line, node_line, optional = _REQUIREMENT_TEXT[lang]
        platforms = _localized(python, "platforms", lang)
        node_range = _localized(node, "range", lang)
        lines = [
            f"- {python_line.format(range=python['range'], platforms=platforms)}",
            f"- {node_line.format(range=node_range)}",
        ]
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
            "| --- | --- | --- |",
        ]
        for trigger, guide, texts in _TRIGGER_ROWS:
            prereq, summary = texts[lang]
            lines.append(f"| [`{trigger}`]({guide}) | {prereq} | {summary} |")
        return "\n".join(lines)

    @env.macro
    def agents_table(lang: str = "en") -> str:
        lang = _lang(lang)
        header = _AGENT_HEADERS[lang]
        lines = [
            "| " + " | ".join(header) + " |",
            "| --- | --- | --- | --- | --- |",
        ]
        # An em dash marks an option the agent rejects; each agent page explains why.
        for name, provider, executable, guide, agent, effort in _AGENT_ROWS:
            agent_cell = f"`{agent}`" if agent else "—"
            effort_cell = f"`{effort}`" if effort else "—"
            lines.append(
                f"| [{name}]({guide}) | `{provider}` | `{executable}` | {agent_cell} | {effort_cell} |"
            )
        return "\n".join(lines)
