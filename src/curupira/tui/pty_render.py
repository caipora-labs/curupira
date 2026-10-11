"""Render a pyte screen buffer as Rich text for Textual."""

from __future__ import annotations

from pyte.screens import Char, Screen
from rich.style import Style
from rich.text import Text

_ANSI_COLOR_ALIASES: dict[str, str] = {
    "brown": "yellow",
    "brightbrown": "bright_yellow",
    "brightblack": "bright_black",
    "brightred": "bright_red",
    "brightgreen": "bright_green",
    "brightblue": "bright_blue",
    "brightmagenta": "bright_magenta",
    "brightcyan": "bright_cyan",
    "brightwhite": "bright_white",
}


def _resolve_color(name: str) -> str | None:
    """Map a pyte color token to a Rich color string."""
    if name == "default":
        return None
    if len(name) == 6 and all(char in "0123456789abcdefABCDEF" for char in name):
        return f"#{name}"
    return _ANSI_COLOR_ALIASES.get(name, name)


def _char_style(char: Char) -> Style:
    """Build a Rich style for one pyte cell."""
    return Style(
        color=_resolve_color(char.fg),
        bgcolor=_resolve_color(char.bg),
        bold=char.bold,
        italic=char.italics,
        underline=char.underscore,
        strike=char.strikethrough,
        blink=char.blink,
        reverse=char.reverse,
    )


def render_emulator(
    emulator: Screen,
    *,
    show_cursor: bool,
) -> Text:
    """Render the visible pyte buffer, optionally marking the cursor cell.

    Args:
        emulator: Active pyte screen (not named ``screen``; Textual owns that).
        show_cursor: Whether to reverse the cell under the cursor.

    Returns:
        A Rich ``Text`` suitable for a Textual widget ``render`` method.
    """
    output = Text()
    cursor_x = emulator.cursor.x
    cursor_y = emulator.cursor.y
    for row_index in range(emulator.lines):
        if row_index:
            output.append("\n")
        row = emulator.buffer[row_index]
        for column_index in range(emulator.columns):
            char = row[column_index]
            style = _char_style(char)
            if show_cursor and row_index == cursor_y and column_index == cursor_x:
                # Toggle reverse so the cursor stays visible on reverse-video cells.
                style = style + Style(reverse=not bool(style.reverse))
            output.append(char.data, style=style)
    return output
