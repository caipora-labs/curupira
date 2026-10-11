"""Persist ``[assistant]`` preferences into the Curupira TOML configuration."""

from __future__ import annotations

import re
from pathlib import Path

_SECTION_HEADER = re.compile(r"^\[([^\]]+)\]\s*(?:#.*)?$", re.MULTILINE)
_AGENT_LINE = re.compile(r"^(\s*)agent\s*=\s*.*$", re.MULTILINE)
_MODEL_LINE = re.compile(r"^(\s*)model\s*=\s*.*$", re.MULTILINE)


def persist_assistant_agent(
    config_path: Path,
    *,
    agent: str,
    model: str | None = None,
) -> None:
    """Write ``assistant.agent`` (and optional ``model``) into an existing TOML file.

    Updates an existing ``[assistant]`` table in place when present; otherwise appends
    one. Other tables and comments outside that section are left untouched. Does not
    invent a second state file: the path is the same settings TOML Curupira already
    loads.

    Args:
        config_path: Existing Curupira configuration file.
        agent: Registered coding-agent provider name.
        model: Optional model id to store; when ``None``, any existing ``model`` line
            in the ``[assistant]`` table is removed so the unset default applies.

    Raises:
        FileNotFoundError: If ``config_path`` is not an existing file.
        ValueError: If ``agent`` is empty after stripping.
    """
    path = config_path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"configuration file not found: {path}")
    normalized = agent.strip()
    if not normalized:
        raise ValueError("assistant.agent must be a non-empty provider name")

    text = path.read_text(encoding="utf-8")
    section = _assistant_span(text)
    if section is None:
        suffix = "" if text.endswith("\n") or not text else "\n"
        body = _render_assistant_table(normalized, model)
        path.write_text(f"{text}{suffix}\n{body}", encoding="utf-8")
        return

    start, end = section
    updated = _rewrite_assistant_section(text[start:end], normalized, model)
    path.write_text(f"{text[:start]}{updated}{text[end:]}", encoding="utf-8")


def _assistant_span(text: str) -> tuple[int, int] | None:
    """Return the ``[start, end)`` byte offsets of the ``[assistant]`` table body."""
    headers = list(_SECTION_HEADER.finditer(text))
    for index, match in enumerate(headers):
        if match.group(1) != "assistant":
            continue
        start = match.start()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        return start, end
    return None


def _render_assistant_table(agent: str, model: str | None) -> str:
    """Render a complete ``[assistant]`` table."""
    lines = ["[assistant]", f'agent = "{_escape_toml_string(agent)}"']
    if model is not None:
        lines.append(f'model = "{_escape_toml_string(model)}"')
    return "\n".join(lines) + "\n"


def _rewrite_assistant_section(section: str, agent: str, model: str | None) -> str:
    """Replace ``agent`` / ``model`` lines inside an existing ``[assistant]`` section."""
    agent_line = f'agent = "{_escape_toml_string(agent)}"'
    if _AGENT_LINE.search(section):
        section = _AGENT_LINE.sub(agent_line, section, count=1)
    else:
        section = section.rstrip("\n") + f"\n{agent_line}\n"

    if model is None:
        section = _MODEL_LINE.sub("", section)
        section = re.sub(r"\n{3,}", "\n\n", section)
        if not section.endswith("\n"):
            section += "\n"
        return section

    model_line = f'model = "{_escape_toml_string(model)}"'
    if _MODEL_LINE.search(section):
        section = _MODEL_LINE.sub(model_line, section, count=1)
    else:
        section = section.rstrip("\n") + f"\n{model_line}\n"
    if not section.endswith("\n"):
        section += "\n"
    return section


def _escape_toml_string(value: str) -> str:
    """Escape a value for a basic TOML double-quoted string."""
    return value.replace("\\", "\\\\").replace('"', '\\"')
