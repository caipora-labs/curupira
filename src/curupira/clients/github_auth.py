"""Obtain a GitHub API token from the authenticated GitHub CLI."""

from __future__ import annotations

import time

from curupira.clients.process import AsyncProcessRunner
from curupira.errors import CliExecutionError, CliOutputError
from curupira.models import CommandRequest

_TOKEN_CACHE_SECONDS = 300.0


class GitHubCliTokenProvider:
    """Resolve a bearer token through ``gh auth token`` without managing login."""

    def __init__(self, runner: AsyncProcessRunner | None = None) -> None:
        self._runner = runner or AsyncProcessRunner()
        self._token: str | None = None
        self._expires_at = 0.0

    async def get_token(self) -> str:
        """Return a cached token or refresh it from the authenticated ``gh`` CLI."""
        now = time.monotonic()
        if self._token is not None and now < self._expires_at:
            return self._token
        result = await self._runner.run(
            CommandRequest(executable="gh", arguments=("auth", "token"))
        )
        if result.returncode != 0:
            raise CliExecutionError("gh", result.returncode, result.stderr)
        token = result.stdout.strip()
        if not token:
            raise CliOutputError("gh auth token returned an empty token")
        self._token = token
        self._expires_at = now + _TOKEN_CACHE_SECONDS
        return token
