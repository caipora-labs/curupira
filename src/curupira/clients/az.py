"""Typed asynchronous client for the Azure CLI DevOps extension."""

from __future__ import annotations

import asyncio
import json
import re

from pydantic import TypeAdapter, ValidationError
from pyresilience import RetryConfig, resilient

from curupira.clients.process import AsyncProcessRunner
from curupira.errors import (
    CliExecutionError,
    CliOutputError,
    TransientCliError,
)
from curupira.models import AzPullRequest, AzPullRequestSearchRequest, CommandRequest

_TRANSIENT_ERROR_MARKERS = (
    "rate limit",
    "connection reset",
    "connection refused",
    "temporary failure",
    "could not resolve",
    "timed out",
    "timeout",
    "tls handshake",
    "network is unreachable",
    "service unavailable",
)


def organization_url(organization: str) -> str:
    """Normalize an organization name or URL for ``az repos``."""
    value = organization.strip().rstrip("/")
    if value.startswith(("https://", "http://")):
        return value
    return f"https://dev.azure.com/{value}"


def branch_name(ref: str | None) -> str | None:
    """Strip the Azure ``refs/heads/`` prefix from a branch ref."""
    if ref is None:
        return None
    prefix = "refs/heads/"
    return ref.removeprefix(prefix)


def _is_transient_cli_error(stderr: str) -> bool:
    message = stderr.lower()
    return any(marker in message for marker in _TRANSIENT_ERROR_MARKERS) or bool(
        re.search(r"\b(?:429|502|503|504|5\d\d)\b", message)
    )


class AzClient:
    """List Azure DevOps pull requests through ``az repos pr list``."""

    def __init__(self, runner: AsyncProcessRunner | None = None) -> None:
        self._runner = runner or AsyncProcessRunner()
        self._search_lock = asyncio.Lock()

    async def list_pull_requests(self, request: AzPullRequestSearchRequest) -> list[AzPullRequest]:
        """List pull requests through the resilient Azure CLI boundary."""
        payload = await self._list_pull_requests_resilient(request)
        try:
            return TypeAdapter(list[AzPullRequest]).validate_python(payload)
        except ValidationError as error:
            raise CliOutputError(f"az returned invalid pull request JSON: {error}") from error

    @resilient(
        retry=RetryConfig(
            max_attempts=3,
            delay=1.0,
            backoff_factor=2.0,
            max_delay=5.0,
            jitter=True,
            retry_on=(TransientCliError,),
        )
    )
    async def _list_pull_requests_resilient(
        self, request: AzPullRequestSearchRequest
    ) -> list[object]:
        arguments = [
            "repos",
            "pr",
            "list",
            "--organization",
            organization_url(request.organization),
            "--project",
            request.project,
            "--repository",
            request.repository,
            "--status",
            request.status,
            "--top",
            str(request.limit),
            "--include-links",
            "--output",
            "json",
        ]
        if request.source_branch is not None:
            arguments.extend(("--source-branch", request.source_branch))
        if request.target_branch is not None:
            arguments.extend(("--target-branch", request.target_branch))

        async with self._search_lock:
            result = await self._runner.run(
                CommandRequest(executable="az", arguments=tuple(arguments))
            )
        if result.returncode != 0:
            if _is_transient_cli_error(result.stderr):
                raise TransientCliError(
                    "az temporarily failed with status "
                    f"{result.returncode}: {result.stderr.strip()}"
                )
            raise CliExecutionError("az", result.returncode, result.stderr)

        try:
            content = result.stdout.strip()
            if not content:
                return []
            payload = json.loads(content)
            if not isinstance(payload, list):
                raise TypeError("expected a JSON array of pull requests")
            if not all(isinstance(item, dict) for item in payload):
                raise TypeError("expected each pull request to be a JSON object")
            return payload
        except (json.JSONDecodeError, TypeError) as error:
            raise CliOutputError(f"az returned invalid pull request JSON: {error}") from error
