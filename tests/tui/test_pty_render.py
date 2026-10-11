"""Unit tests for pyte-buffer rendering into Rich text."""

import pyte
from rich.console import Console

from curupira.tui.pty_render import render_emulator


def test_render_emulator_applies_sgr_truecolor_reverse_and_cursor() -> None:
    emulator = pyte.Screen(10, 2)
    stream = pyte.ByteStream(emulator)
    stream.feed(b"\x1b[1;38;2;255;0;0mR\x1b[0m\x1b[7mX\x1b[0m")

    rendered = render_emulator(emulator, show_cursor=True)
    assert rendered.plain.startswith("RX")
    console = Console(force_terminal=True, color_system="truecolor")

    red = rendered.get_style_at_offset(console, 0)
    assert red.bold
    assert red.color is not None
    assert red.color.triplet is not None
    assert red.color.triplet.red == 255
    assert red.color.triplet.green == 0
    assert red.color.triplet.blue == 0

    reversed_cell = rendered.get_style_at_offset(console, 1)
    assert reversed_cell.reverse

    cursor_cell = rendered.get_style_at_offset(console, 2)
    assert cursor_cell.reverse


def test_cursor_toggles_reverse_on_reverse_video_cell() -> None:
    emulator = pyte.Screen(4, 1)
    stream = pyte.ByteStream(emulator)
    stream.feed(b"\x1b[7mZ")
    # Cursor rests on the reverse-video cell.
    emulator.cursor.x = 0
    emulator.cursor.y = 0

    without_cursor = render_emulator(emulator, show_cursor=False)
    with_cursor = render_emulator(emulator, show_cursor=True)
    console = Console(force_terminal=True, color_system="truecolor")

    assert without_cursor.get_style_at_offset(console, 0).reverse
    # Toggling reverse makes the cursor visible on an already-reversed cell.
    assert not with_cursor.get_style_at_offset(console, 0).reverse
