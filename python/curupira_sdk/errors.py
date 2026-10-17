"""SDK and JSON-RPC errors."""

from __future__ import annotations

from typing import Any


class RegistrationError(Exception):
    """Raised when a trigger cannot be registered."""


class ValidationError(Exception):
    """Raised when configuration or arguments fail validation."""


class SerializationError(Exception):
    """Raised when a trigger return value cannot be serialized."""


class RpcError(Exception):
    """JSON-RPC error with numeric code."""

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.data = data
