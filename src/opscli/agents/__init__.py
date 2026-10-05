"""Coding-agent adapters and provider factory."""

from opscli.agents.base import (
    CliAdapterFactory as CliAdapterFactory,
)
from opscli.agents.base import (
    CodingAgentCliAdapter,
)
from opscli.clients.process import AsyncProcessRunner
from opscli.errors import UnsupportedCodingAgentError


def create_cli_adapter(
    provider: str, runner: AsyncProcessRunner | None = None
) -> CodingAgentCliAdapter:
    """Construct the native adapter for a supported provider."""
    from opscli.agents.codex import CodexCliAdapter
    from opscli.agents.cursor import CursorCliAdapter
    from opscli.clients.claude import ClaudeCodeCliAdapter
    from opscli.clients.opencode import OpenCodeCliAdapter

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
