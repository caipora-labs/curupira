"""Typed asynchronous client for the GitHub CLI."""

from __future__ import annotations

import asyncio
import json
import re
from typing import cast

from pydantic import TypeAdapter, ValidationError
from pyresilience import RetryConfig, resilient

from gh_dispatch.clients.process import AsyncProcessRunner
from gh_dispatch.errors import (
    CliExecutionError,
    CliOutputError,
    TransientCliError,
)
from gh_dispatch.models import (
    DEFAULT_ISSUE_JSON_FIELDS,
    CommandRequest,
    GhIssue,
    GhIssueSearchRequest,
    GhPullRequest,
    GhPullRequestSearchRequest,
)

_PROJECT_ITEM_JSON_FIELDS = ("number", "title", "url", "projectItems")
_PROJECT_ITEM_JQ_FILTER = '.[] | select(any(.projectItems[]?; .status.name == "Todo"))'
_DEFAULT_PULL_REQUEST_JSON_FIELDS = (
    "number",
    "title",
    "body",
    "url",
    "state",
    "labels",
    "isDraft",
    "headRefName",
    "baseRefName",
)
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
)


def _is_transient_cli_error(stderr: str) -> bool:
    message = stderr.lower()
    return any(marker in message for marker in _TRANSIENT_ERROR_MARKERS) or bool(
        re.search(r"\b(?:429|502|503|504|5\d\d)\b", message)
    )


class GhClient:
    """Search GitHub issues through ``gh issue list``."""

    def __init__(self, runner: AsyncProcessRunner | None = None) -> None:
        self._runner = runner or AsyncProcessRunner()
        self._search_lock = asyncio.Lock()

    async def list_issues(self, request: GhIssueSearchRequest) -> list[GhIssue]:
        """List issues through the resilient gh boundary."""
        payload = await self._list_issues_resilient(request)
        try:
            return TypeAdapter(list[GhIssue]).validate_python(payload)
        except ValidationError as error:
            raise CliOutputError(f"gh returned invalid issue JSON: {error}") from error

    async def list_pull_requests(self, request: GhPullRequestSearchRequest) -> list[GhPullRequest]:
        """List pull requests through the resilient gh boundary."""
        payload = await self._list_pull_requests_resilient(request)
        try:
            return TypeAdapter(list[GhPullRequest]).validate_python(payload)
        except ValidationError as error:
            raise CliOutputError(f"gh returned invalid pull request JSON: {error}") from error

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
    async def _list_issues_resilient(self, request: GhIssueSearchRequest) -> list[object]:
        return await self._search_items(
            "issue",
            request.repo,
            request.query,
            request.limit,
            DEFAULT_ISSUE_JSON_FIELDS,
        )

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
        self, request: GhPullRequestSearchRequest
    ) -> list[object]:
        return await self._search_items(
            "pr",
            request.repo,
            request.query,
            request.limit,
            _DEFAULT_PULL_REQUEST_JSON_FIELDS,
        )

    async def _search_items(
        self,
        command: str,
        repo: str,
        query: str,
        limit: int,
        default_fields: tuple[str, ...],
    ) -> list[object]:
        arguments = [
            command,
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--search",
            query,
            "--limit",
            str(limit),
            "--json",
            ",".join(_PROJECT_ITEM_JSON_FIELDS if _is_project_query(query) else default_fields),
        ]
        if _is_project_query(query):
            arguments.extend(("--jq", _PROJECT_ITEM_JQ_FILTER))

        async with self._search_lock:
            result = await self._runner.run(
                CommandRequest(executable="gh", arguments=tuple(arguments))
            )
        if result.returncode != 0:
            if _is_transient_cli_error(result.stderr):
                raise TransientCliError(
                    "gh temporarily failed with status "
                    f"{result.returncode}: {result.stderr.strip()}"
                )
            raise CliExecutionError("gh", result.returncode, result.stderr)

        try:
            payload = _decode_json_output(result.stdout)
            if not isinstance(payload, list):
                payload = [payload]
            if not all(isinstance(item, dict) for item in payload):
                raise TypeError("expected each jq result to be a JSON object")
            return payload
        except (json.JSONDecodeError, TypeError) as error:
            raise CliOutputError(f"gh returned invalid {command} JSON: {error}") from error


def _is_project_query(query: str) -> bool:
    return re.search(r"(?:^|\s)project:\S+", query, flags=re.IGNORECASE) is not None


def _decode_json_output(output: str) -> object:
    """Decode either gh's JSON array or jq's newline-delimited JSON results."""
    content = output.strip()
    if not content:
        return cast(list[object], [])

    try:
        return json.loads(content)
    except json.JSONDecodeError as first_error:
        decoder = json.JSONDecoder()
        values: list[object] = []
        offset = 0
        while offset < len(content):
            while offset < len(content) and content[offset].isspace():
                offset += 1
            if offset == len(content):
                break
            try:
                value, offset = decoder.raw_decode(content, offset)
            except json.JSONDecodeError:
                raise first_error from None
            values.append(value)
        return values
