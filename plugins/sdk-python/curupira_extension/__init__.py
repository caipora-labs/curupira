"""Minimal SDK for Curupira process extensions (JSON-RPC 2.0, length-prefixed frames)."""

from .server import ExtensionServer, serve_stdio
from .framing import read_frame, write_frame

__all__ = ["ExtensionServer", "serve_stdio", "read_frame", "write_frame"]
