"""Typed asynchronous client for the GitHub CLI."""

from __future__ import annotations

import asyncio
import json
import re
from typing import cast

from pydantic import TypeAdapter, ValidationError
from pyresilience import RetryConfig, resilient

from curupira.clients.process import AsyncProcessRunner
from curupira.errors import (
    CliExecutionError,
    CliOutputError,
    TransientCliError,
)
from curupira.models import (
    DEFAULT_ISSUE_JSON_FIELDS,
    CommandRequest,
    GhIssue,
    GhIssueSearchRequest,
    GhPullRequest,
    GhPullRequestSearchRequest,
    Task,
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
    "mergeable",
    "mergeStateStatus",
    "headRefOid",
    "closingIssuesReferences",
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

    async def revalidate_task(self, task: Task) -> Task | None:
        """Return the current open task, suppressing issues with any linked open PR."""
        identity = task.identity
        if identity.task_type == "issue":
            issues = await self.list_issues(
                GhIssueSearchRequest(
                    repo=identity.repo, query=f"is:open number:{identity.id}", limit=1
                )
            )
            if not issues:
                return None
            open_pulls = await self.list_pull_requests(
                GhPullRequestSearchRequest(repo=identity.repo, query="is:open", limit=1000)
            )
            if any(
                reference.number == int(identity.id)
                for pull in open_pulls
                for reference in pull.closing_issues_references
            ):
                return None
            issue = issues[0]
            return task.model_copy(
                update={"title": issue.title, "body": issue.body, "url": issue.url}
            )
        if identity.task_type != "github-cli-pull-requests":
            return task
        pulls = await self.list_pull_requests(
            GhPullRequestSearchRequest(
                repo=identity.repo, query=f"is:open number:{identity.id}", limit=1
            )
        )
        if not pulls:
            return None
        pull = pulls[0]
        priority = _pull_request_priority(pull.is_draft, pull.mergeable, pull.merge_state_status)
        return task.model_copy(
            update={
                "title": pull.title,
                "body": pull.body,
                "url": pull.url,
                "is_draft": pull.is_draft,
                "head_ref_name": pull.head_ref_name,
                "head_ref_oid": pull.head_ref_oid,
                "base_ref_name": pull.base_ref_name,
                "workflow_priority": priority,
            }
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
            request.jq,
        )

    async def _search_items(
        self,
        command: str,
        repo: str,
        query: str,
        limit: int,
        default_fields: tuple[str, ...],
        jq: str | None = None,
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
        jq_filter = _PROJECT_ITEM_JQ_FILTER if _is_project_query(query) else None
        if jq is not None:
            jq_filter = f"({jq_filter}) | ({jq})" if jq_filter is not None else jq
        if jq_filter is not None:
            arguments.extend(("--jq", jq_filter))

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


def _pull_request_priority(
    is_draft: bool | None, mergeable: str | None, merge_state: str | None
) -> int:
    if is_draft:
        return 3
    if merge_state == "DIRTY" or mergeable == "CONFLICTING":
        return 1
    if merge_state == "CLEAN" and mergeable == "MERGEABLE":
        return 0
    return 2


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
