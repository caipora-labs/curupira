"""Declarative SDK for Curupira process extensions."""

from __future__ import annotations

from .app import Curupira
from .errors import RegistrationError, RpcError, SerializationError, ValidationError
from .framing import read_frame, write_frame
from .server import ExtensionServer, serve_stdio

__all__ = [
    "Curupira",
    "ExtensionServer",
    "RegistrationError",
    "RpcError",
    "SerializationError",
    "ValidationError",
    "read_frame",
    "serve_stdio",
    "write_frame",
]

__version__ = "0.2.0"
