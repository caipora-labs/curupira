"""Length-prefixed JSON frames (8 hex digits + body)."""

from __future__ import annotations

import sys
from typing import BinaryIO

DEFAULT_MAX_FRAME_BYTES = 16 * 1024 * 1024


def write_frame(writer: BinaryIO, payload: bytes) -> None:
    """Write one frame to a binary writer (typically stdout.buffer)."""
    if len(payload) > 0xFFFFFFFF:
        raise ValueError("frame too large")
    writer.write(f"{len(payload):08x}".encode("ascii"))
    writer.write(payload)
    writer.flush()


def read_frame(reader: BinaryIO, max_bytes: int = DEFAULT_MAX_FRAME_BYTES) -> bytes:
    """Read one frame from a binary reader (typically stdin.buffer)."""
    header = reader.read(8)
    if len(header) < 8:
        raise EOFError("unexpected EOF while reading frame header")
    try:
        length = int(header.decode("ascii"), 16)
    except ValueError as exc:
        raise ValueError("invalid frame header") from exc
    if length > max_bytes:
        raise ValueError(f"frame length {length} exceeds limit {max_bytes}")
    body = reader.read(length)
    if len(body) < length:
        raise EOFError("unexpected EOF while reading frame body")
    return body


def log(message: str) -> None:
    """Write a diagnostic line to stderr (never stdout)."""
    print(message, file=sys.stderr, flush=True)
