"""Coding-agent adapters and provider factory."""

from gh_dispatch.agents.base import (
    CliAdapterFactory as CliAdapterFactory,
)
from gh_dispatch.agents.base import (
    CodingAgentCliAdapter,
)
from gh_dispatch.clients.process import AsyncProcessRunner
from gh_dispatch.errors import UnsupportedCodingAgentError


def create_cli_adapter(
    provider: str, runner: AsyncProcessRunner | None = None
) -> CodingAgentCliAdapter:
    """Construct the native adapter for a supported provider."""
    from gh_dispatch.clients.claude import ClaudeCodeCliAdapter
    from gh_dispatch.clients.codex import CodexCliAdapter
    from gh_dispatch.clients.cursor import CursorCliAdapter
    from gh_dispatch.clients.opencode import OpenCodeCliAdapter

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
