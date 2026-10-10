"""Coding-agent adapters and provider factory."""

# Import concrete adapters so registry lookups work regardless of which application
# entry point is used first.
from curupira.agents import (  # noqa: F401
    claude,
    codex,
    copilot,
    cursor,
    gemini,
    kilo,
    opencode,
    pi,
    qwen,
)
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
