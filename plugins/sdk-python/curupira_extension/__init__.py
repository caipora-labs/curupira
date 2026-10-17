"""Minimal SDK for Curupira process extensions (JSON-RPC 2.0, length-prefixed frames)."""

from .framing import read_frame, write_frame
from .server import ExtensionServer, serve_stdio

__all__ = ["ExtensionServer", "read_frame", "serve_stdio", "write_frame"]
