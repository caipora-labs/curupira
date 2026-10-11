"""Unit tests for Textual-to-PTY key and paste encoding."""

from textual.events import Key

from curupira.tui.pty_keys import (
    bracketed_paste_enabled,
    key_to_bytes,
    paste_to_bytes,
)


def test_arrow_and_editing_keys_use_xterm_sequences() -> None:
    assert key_to_bytes(Key("up", character=None)) == b"\x1b[A"
    assert key_to_bytes(Key("home", character=None)) == b"\x1b[H"
    assert key_to_bytes(Key("end", character=None)) == b"\x1b[F"
    assert key_to_bytes(Key("pageup", character=None)) == b"\x1b[5~"
    assert key_to_bytes(Key("pagedown", character=None)) == b"\x1b[6~"
    assert key_to_bytes(Key("backspace", character=None)) == b"\x7f"
    assert key_to_bytes(Key("tab", character="\t")) == b"\t"
    assert key_to_bytes(Key("shift+tab", character=None)) == b"\x1b[Z"
    assert key_to_bytes(Key("enter", character="\r")) == b"\r"
    assert key_to_bytes(Key("escape", character=None)) == b"\x1b"


def test_function_keys_and_modifiers() -> None:
    assert key_to_bytes(Key("f1", character=None)) == b"\x1bOP"
    assert key_to_bytes(Key("f12", character=None)) == b"\x1b[24~"
    assert key_to_bytes(Key("ctrl+c", character="\x03")) == b"\x03"
    assert key_to_bytes(Key("alt+a", character=None)) == b"\x1ba"
    assert key_to_bytes(Key("a", character="a")) == b"a"


def test_bracketed_paste_wrapping_follows_mode_flag() -> None:
    assert paste_to_bytes("hi", bracketed=False) == b"hi"
    assert paste_to_bytes("hi", bracketed=True) == b"\x1b[200~hi\x1b[201~"
    assert bracketed_paste_enabled({2004 << 5})
    assert not bracketed_paste_enabled(set())
