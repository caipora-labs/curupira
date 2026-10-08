"""Coding-agent adapters and provider factory."""

from curupira.agents.base import CliAdapterFactory, CodingAgentCliAdapter
from curupira.agents.claude import ClaudeCodeCliAdapter
from curupira.agents.codex import CodexCliAdapter
from curupira.agents.cursor import CursorCliAdapter
from curupira.agents.opencode import OpenCodeCliAdapter
from curupira.clients.process import AsyncProcessRunner
from curupira.errors import UnsupportedCodingAgentError

__all__ = ["CliAdapterFactory", "CodingAgentCliAdapter", "create_cli_adapter"]

_ADAPTERS: dict[str, type[CodingAgentCliAdapter]] = {
    adapter.provider: adapter
    for adapter in (OpenCodeCliAdapter, CodexCliAdapter, ClaudeCodeCliAdapter, CursorCliAdapter)
}


def create_cli_adapter(
    provider: str, runner: AsyncProcessRunner | None = None
) -> CodingAgentCliAdapter:
    """Construct the native adapter for a supported provider."""
    try:
        adapter = _ADAPTERS[provider]
    except KeyError as error:
        raise UnsupportedCodingAgentError(
            f"unsupported coding agent provider: {provider}"
        ) from error
    return adapter(runner)
