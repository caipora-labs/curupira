"""Persist ``[assistant]`` preferences into the Curupira TOML configuration.

Only a standard unquoted ``[assistant]`` table is rewritten in place. Inline
tables (``assistant = {…}``), dotted keys (``assistant.agent = …``), and quoted
headers (``["assistant"]``) are refused without modifying the file so Curupira
never appends a second ``assistant`` declaration that would invalidate the TOML
and stall hot-reload admissions.

Writes are atomic (temp file in the same directory + ``os.replace``) and preserve
the destination file mode and newline style (LF or CRLF). End-of-line comments on
existing ``agent`` / ``model`` lines are kept when those keys are rewritten.
"""

from __future__ import annotations

import contextlib
import os
import re
import stat
import tempfile
import tomllib
from pathlib import Path

_SECTION_HEADER = re.compile(r"^\[([^\]]+)\]\s*(?:#.*)?$", re.MULTILINE)
_AGENT_LINE = re.compile(r"^(\s*)agent\s*=\s*([^#\n]*?)(\s*#.*)?$", re.MULTILINE)
# Consume the trailing newline (or end-of-string) so removing ``model`` does not
# leave a blank line. The value group stays non-greedy; ``(?:\n|$)`` forces it to
# extend to the real end of the line (unlike a bare ``\n?``, which under-matches).
_MODEL_LINE = re.compile(r"^(\s*)model\s*=\s*([^#\n]*?)(\s*#.*)?(?:\n|$)", re.MULTILINE)
_INLINE_ASSISTANT = re.compile(r"^\s*assistant\s*=\s*\{", re.MULTILINE)
_DOTTED_ASSISTANT = re.compile(r"^\s*assistant\.[A-Za-z0-9_-]+\s*=", re.MULTILINE)
_QUOTED_ASSISTANT_HEADER = re.compile(
    r"""^\s*\[["']assistant["']\]\s*(?:#.*)?$""",
    re.MULTILINE,
)

_UNSUPPORTED_MESSAGE = (
    "assistant settings use an unsupported TOML shape (inline table, dotted key, "
    "or quoted header); use a standard [assistant] table, or omit it so Curupira "
    "can append one"
)


class UnsupportedAssistantTomlError(ValueError):
    """Raised when ``assistant`` is declared in a shape this writer will not touch."""


def persist_assistant_agent(
    config_path: Path,
    *,
    agent: str,
    model: str | None = None,
) -> None:
    """Write ``assistant.agent`` (and optional ``model``) into an existing TOML file.

    Updates an existing standard ``[assistant]`` table in place when present;
    otherwise appends one. Refuses (without writing) when ``assistant`` already
    exists as an inline table, dotted keys, or a quoted header. Other tables and
    comments outside that section are left untouched. Does not invent a second
    state file: the path is the same settings TOML Curupira already loads.

    The file's newline style (LF or CRLF) is detected from the existing bytes and
    preserved on write; processing always uses ``\\n`` internally.

    Args:
        config_path: Existing Curupira configuration file.
        agent: Registered coding-agent provider name.
        model: Optional model id to store; when ``None``, any existing ``model`` line
            in the ``[assistant]`` table is removed so the unset default applies.

    Raises:
        FileNotFoundError: If ``config_path`` is not an existing file.
        ValueError: If ``agent`` is empty after stripping.
        UnsupportedAssistantTomlError: If ``assistant`` uses an unsupported shape.
        OSError: If the atomic replace fails (for example permission denied).
    """
    path = config_path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"configuration file not found: {path}")
    normalized = agent.strip()
    if not normalized:
        raise ValueError("assistant.agent must be a non-empty provider name")

    text, newline = _read_text_with_newline(path)
    kind = _assistant_shape(text)
    if kind == "unsupported":
        raise UnsupportedAssistantTomlError(_UNSUPPORTED_MESSAGE)

    if kind == "absent":
        suffix = "" if text.endswith("\n") or not text else "\n"
        body = _render_assistant_table(normalized, model)
        _atomic_write(path, f"{text}{suffix}\n{body}", newline=newline)
        return

    span = _assistant_span(text)
    if span is None:
        # Defensive: _assistant_shape reported standard but the header vanished.
        raise UnsupportedAssistantTomlError(_UNSUPPORTED_MESSAGE)
    start, end = span
    updated = _rewrite_assistant_section(text[start:end], normalized, model)
    _atomic_write(path, f"{text[:start]}{updated}{text[end:]}", newline=newline)


def _read_text_with_newline(path: Path) -> tuple[str, str]:
    """Return ``(text_with_lf, newline)`` without collapsing CRLF across the file.

    ``newline`` is ``\"\\r\\n\"`` when the raw bytes contain CRLF, otherwise ``\"\\n\"``.
    The returned text always uses ``\\n`` so regex rewrites stay newline-agnostic.
    """
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8")
    if newline == "\r\n":
        text = text.replace("\r\n", "\n")
    return text, newline


def _assistant_shape(text: str) -> str:
    """Classify how ``assistant`` appears in the TOML source.

    Returns:
        ``\"standard\"`` for an unquoted ``[assistant]`` table header,
        ``\"absent\"`` when no assistant declaration is present,
        ``\"unsupported\"`` for inline / dotted / quoted forms (or any parse that
        yields an ``assistant`` key without a standard header).
    """
    if _INLINE_ASSISTANT.search(text) or _DOTTED_ASSISTANT.search(text):
        return "unsupported"
    if _QUOTED_ASSISTANT_HEADER.search(text):
        return "unsupported"

    standard = _assistant_span(text) is not None
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        # Leave invalid files alone; the caller should not rewrite them.
        return "unsupported"

    has_key = isinstance(data.get("assistant"), dict)
    if standard:
        return "standard"
    if has_key:
        return "unsupported"
    return "absent"


def _assistant_span(text: str) -> tuple[int, int] | None:
    """Return the ``[start, end)`` offsets of a standard ``[assistant]`` table."""
    headers = list(_SECTION_HEADER.finditer(text))
    for index, match in enumerate(headers):
        if match.group(1) != "assistant":
            continue
        start = match.start()
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        return start, end
    return None


def _render_assistant_table(agent: str, model: str | None) -> str:
    """Render a complete ``[assistant]`` table (LF separators)."""
    lines = ["[assistant]", f'agent = "{_escape_toml_string(agent)}"']
    if model is not None:
        lines.append(f'model = "{_escape_toml_string(model)}"')
    return "\n".join(lines) + "\n"


def _rewrite_assistant_section(section: str, agent: str, model: str | None) -> str:
    """Replace ``agent`` / ``model`` lines inside an existing ``[assistant]`` section."""
    agent_value = f'agent = "{_escape_toml_string(agent)}"'
    agent_match = _AGENT_LINE.search(section)
    if agent_match is not None:
        comment = agent_match.group(3) or ""
        section = _AGENT_LINE.sub(f"{agent_match.group(1)}{agent_value}{comment}", section, count=1)
    else:
        section = section.rstrip("\n") + f"\n{agent_value}\n"

    if model is None:
        # _MODEL_LINE consumes the trailing newline so removal does not leave a blank.
        section = _MODEL_LINE.sub("", section)
        if not section.endswith("\n"):
            section += "\n"
        return section

    model_value = f'model = "{_escape_toml_string(model)}"'
    model_match = _MODEL_LINE.search(section)
    if model_match is not None:
        comment = model_match.group(3) or ""
        indent = model_match.group(1)
        # Re-add the newline that _MODEL_LINE consumed.
        section = _MODEL_LINE.sub(f"{indent}{model_value}{comment}\n", section, count=1)
    else:
        section = section.rstrip("\n") + f"\n{model_value}\n"
    if not section.endswith("\n"):
        section += "\n"
    return section


def _atomic_write(path: Path, content: str, *, newline: str = "\n") -> None:
    """Write ``content`` via a temp file in ``path.parent`` and ``os.replace``.

    ``content`` must use ``\\n`` line endings; they are converted to ``newline``
    (``\\n`` or ``\\r\\n``) before writing. Preserves the destination file's
    permission bits (``stat.S_IMODE``).
    """
    mode = stat.S_IMODE(path.stat().st_mode)
    payload = content.replace("\n", newline).encode("utf-8")
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=".curupira-assistant-",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.chmod(mode)
        tmp_path.replace(path)
    except Exception:
        with contextlib.suppress(OSError):
            tmp_path.unlink()
        raise


def _escape_toml_string(value: str) -> str:
    """Escape a value for a basic TOML double-quoted string."""
    return value.replace("\\", "\\\\").replace('"', '\\"')
