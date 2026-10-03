"""Abstract coding-agent interface and provider factory."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from gh_dispatch.clients.process import AsyncProcessRunner
from gh_dispatch.errors import UnsupportedCodingAgentError
from gh_dispatch.models import (
    CodingAgentProfile,
    CodingAgentsSettings,
    CodingTaskRequest,
    ProcessResult,
)

SessionStartedCallback = Callable[[str], Awaitable[None]]
RESUME_SESSION_PROMPT = (
    "Continue the interrupted task from this session. Review the existing conversation and "
    "repository state, then complete the requested work without repeating completed steps."
)


class CodingAgent(ABC):
    """Common asynchronous interface implemented by coding-agent adapters."""

    @abstractmethod
    async def run_task(
        self,
        request: CodingTaskRequest,
        *,
        on_session_started: SessionStartedCallback | None = None,
    ) -> ProcessResult:
        """Run one task using the selected agent profile."""


CodingAgentFactory = Callable[[str], CodingAgent]


def resolve_coding_agent_profile(
    settings: CodingAgentsSettings,
    profile_name: str | None,
) -> CodingAgentProfile:
    name = profile_name or settings.default
    try:
        return settings.profiles[name]
    except KeyError as error:
        raise UnsupportedCodingAgentError(f"coding agent profile not found: {name}") from error


def create_coding_agent(
    provider: str,
    runner: AsyncProcessRunner | None = None,
) -> CodingAgent:
    """Create the adapter for a provider supported by this version."""
    if provider == "opencode":
        from gh_dispatch.clients.opencode import OpenCodeClient

        return OpenCodeClient(runner)
    if provider == "codex":
        from gh_dispatch.clients.codex import CodexClient

        return CodexClient(runner)
    if provider == "claude":
        from gh_dispatch.clients.claude import ClaudeCodeClient

        return ClaudeCodeClient(runner)
    if provider == "cursor":
        from gh_dispatch.clients.cursor import CursorCliClient

        return CursorCliClient(runner)
    raise UnsupportedCodingAgentError(f"unsupported coding agent provider: {provider}")
