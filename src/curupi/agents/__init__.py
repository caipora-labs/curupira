"""Coding-agent adapters and provider factory."""

from curupi.agents.base import (
    CliAdapterFactory as CliAdapterFactory,
)
from curupi.agents.base import (
    CodingAgentCliAdapter,
)
from curupi.clients.process import AsyncProcessRunner
from curupi.errors import UnsupportedCodingAgentError


def create_cli_adapter(
    provider: str, runner: AsyncProcessRunner | None = None
) -> CodingAgentCliAdapter:
    """Construct the native adapter for a supported provider."""
    from curupi.agents.claude import ClaudeCodeCliAdapter
    from curupi.agents.codex import CodexCliAdapter
    from curupi.agents.cursor import CursorCliAdapter
    from curupi.agents.opencode import OpenCodeCliAdapter

    adapters: dict[str, type[CodingAgentCliAdapter]] = {
        "opencode": OpenCodeCliAdapter,
        "codex": CodexCliAdapter,
        "claude": ClaudeCodeCliAdapter,
        "cursor": CursorCliAdapter,
    }
    try:
        adapter = adapters[provider]
    except KeyError as error:
        raise UnsupportedCodingAgentError(
            f"unsupported coding agent provider: {provider}"
        ) from error
    return adapter(runner)
