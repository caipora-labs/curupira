"""Coding-agent adapter factory and stable base types.

Concrete built-in adapters live under ``curupira.providers`` and register through
Pluggy. This package keeps the shared ``CodingAgentCliAdapter`` contract, the
registry, and ``create_cli_adapter`` for application code and plugins.
"""

from curupira.agents.base import (
    CliAdapterFactory as CliAdapterFactory,
)
from curupira.agents.base import (
    CodingAgentCliAdapter,
)
from curupira.clients.process import AsyncProcessRunner
from curupira.errors import UnsupportedCodingAgentError


def create_cli_adapter(
    provider: str, runner: AsyncProcessRunner | None = None
) -> CodingAgentCliAdapter:
    """Construct the registered adapter for a provider."""
    from curupira.agents.registry import get

    try:
        adapter = get(provider)
    except ValueError as error:
        raise UnsupportedCodingAgentError(
            f"unsupported coding agent provider: {provider}"
        ) from error
    return adapter(runner)
