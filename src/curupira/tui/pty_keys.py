"""Map Textual key and paste events to xterm/VT100 byte sequences."""

from __future__ import annotations

from textual.events import Key

_NAMED_KEYS: dict[str, bytes] = {
    "up": b"\x1b[A",
    "down": b"\x1b[B",
    "right": b"\x1b[C",
    "left": b"\x1b[D",
    "home": b"\x1b[H",
    "end": b"\x1b[F",
    "pageup": b"\x1b[5~",
    "pagedown": b"\x1b[6~",
    "insert": b"\x1b[2~",
    "delete": b"\x1b[3~",
    "backspace": b"\x7f",
    "tab": b"\t",
    "shift+tab": b"\x1b[Z",
    "enter": b"\r",
    "escape": b"\x1b",
    "f1": b"\x1bOP",
    "f2": b"\x1bOQ",
    "f3": b"\x1bOR",
    "f4": b"\x1bOS",
    "f5": b"\x1b[15~",
    "f6": b"\x1b[17~",
    "f7": b"\x1b[18~",
    "f8": b"\x1b[19~",
    "f9": b"\x1b[20~",
    "f10": b"\x1b[21~",
    "f11": b"\x1b[23~",
    "f12": b"\x1b[24~",
}

_BRACKETED_PASTE_START = b"\x1b[200~"
_BRACKETED_PASTE_END = b"\x1b[201~"
_BRACKETED_PASTE_MODE = 2004 << 5


def key_to_bytes(event: Key) -> bytes | None:
    """Translate a Textual key event into bytes for the PTY child.

    Args:
        event: Focused-widget key event from Textual.

    Returns:
        Bytes to write to the PTY master, or ``None`` when the key has no
        terminal encoding (for example pointer-only chords).
    """
    named = _NAMED_KEYS.get(event.key)
    if named is not None:
        return named

    if event.key.startswith("ctrl+") and len(event.key) == 6:
        letter = event.key[-1]
        if letter.isalpha():
            return bytes([ord(letter.lower()) - ord("a") + 1])

    if event.key.startswith("alt+") and len(event.key) >= 5:
        suffix = event.key[4:]
        if len(suffix) == 1:
            return b"\x1b" + suffix.encode("utf-8", errors="replace")
        nested = _NAMED_KEYS.get(suffix)
        if nested is not None:
            return b"\x1b" + nested

    if event.character:
        return event.character.encode("utf-8", errors="replace")
    return None


def paste_to_bytes(text: str, *, bracketed: bool) -> bytes:
    """Encode a paste payload, wrapping it when bracketed-paste mode is on.

    Args:
        text: Pasted Unicode text from Textual.
        bracketed: Whether the child enabled DEC mode 2004.

    Returns:
        Bytes to write to the PTY master.
    """
    payload = text.encode("utf-8", errors="replace")
    if not bracketed:
        return payload
    return _BRACKETED_PASTE_START + payload + _BRACKETED_PASTE_END


def bracketed_paste_enabled(modes: set[int]) -> bool:
    """Return whether pyte reports private mode 2004 as active.

    Args:
        modes: The pyte screen ``mode`` set.

    Returns:
        ``True`` when bracketed paste should wrap Textual paste events.
    """
    return _BRACKETED_PASTE_MODE in modes
