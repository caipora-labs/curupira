"""Coding-agent adapters and provider factory."""

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
    """Construct the native adapter for a supported provider."""
    from curupira.agents.claude import ClaudeCodeCliAdapter
    from curupira.agents.codex import CodexCliAdapter
    from curupira.agents.cursor import CursorCliAdapter
    from curupira.agents.opencode import OpenCodeCliAdapter

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
