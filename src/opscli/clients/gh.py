"""Typed asynchronous client for the GitHub CLI."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
from asyncio import to_thread
from pathlib import Path
from typing import cast

from pydantic import TypeAdapter, ValidationError
from pyresilience import RetryConfig, resilient

from opscli.clients.process import AsyncProcessRunner
from opscli.errors import (
    CliExecutionError,
    CliOutputError,
    TransientCliError,
    WorkspacePathError,
)
from opscli.models import (
    DEFAULT_ISSUE_JSON_FIELDS,
    CommandRequest,
    GhIssue,
    GhIssueSearchRequest,
    GhPullRequest,
    GhPullRequestSearchRequest,
    GhRepositoryCheckout,
    GhRepositoryCloneRequest,
    ProcessResult,
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
        self._clone_locks: dict[Path, asyncio.Lock] = {}
        self._worktree_locks: dict[Path, asyncio.Lock] = {}
        self._search_lock = asyncio.Lock()

    async def run_setup_script(
        self,
        checkout: GhRepositoryCheckout,
        script: str,
        *,
        timeout_seconds: float | None = None,
        max_output_bytes: int = 1_000_000,
    ) -> ProcessResult:
        """Execute a repository-relative setup executable directly after a fresh clone."""
        try:
            result = await self._runner.run(
                CommandRequest(
                    executable=str(checkout.path / script),
                    cwd=checkout.path,
                    timeout=timeout_seconds,
                    max_output_bytes=max_output_bytes,
                )
            )
        except Exception:
            if checkout.cloned:
                await to_thread(shutil.rmtree, checkout.path, True)
            raise
        if result.returncode and checkout.cloned:
            await to_thread(shutil.rmtree, checkout.path, True)
        return result

    async def ensure_worktree(
        self, checkout: GhRepositoryCheckout, *, automation_id: str, task_type: str, number: int
    ) -> Path:
        """Create or reuse the task's deterministic worktree from origin's default branch."""
        base = checkout.path
        lock = self._worktree_locks.setdefault(base, asyncio.Lock())
        async with lock:
            target = (
                base.with_name(f"{base.name}.worktrees") / automation_id / f"{task_type}-{number}"
            )
            if target.is_dir():
                return target
            fetch = await self._runner.run(
                CommandRequest(executable="git", arguments=("fetch", "origin"), cwd=base)
            )
            if fetch.returncode:
                raise CliExecutionError("git fetch", fetch.returncode, fetch.stderr)
            default = await self._runner.run(
                CommandRequest(
                    executable="git",
                    arguments=("symbolic-ref", "refs/remotes/origin/HEAD"),
                    cwd=base,
                )
            )
            if default.returncode:
                raise CliExecutionError("git symbolic-ref", default.returncode, default.stderr)
            ref = default.stdout.strip()
            branch = f"opscli/{automation_id}/{task_type}-{number}"
            target.parent.mkdir(parents=True, exist_ok=True)
            result = await self._runner.run(
                CommandRequest(
                    executable="git",
                    arguments=("worktree", "add", "-b", branch, str(target), ref),
                    cwd=base,
                )
            )
            if result.returncode:
                raise CliExecutionError("git worktree add", result.returncode, result.stderr)
            return target

    async def remove_worktree(
        self, checkout: GhRepositoryCheckout, *, automation_id: str, task_type: str, number: int
    ) -> None:
        """Remove a task worktree and its local branch; cleanup failures are best effort."""
        base = checkout.path
        lock = self._worktree_locks.setdefault(base, asyncio.Lock())
        async with lock:
            target = (
                base.with_name(f"{base.name}.worktrees") / automation_id / f"{task_type}-{number}"
            )
            for arguments in (
                ("worktree", "remove", "--force", str(target)),
                ("branch", "-D", f"opscli/{automation_id}/{task_type}-{number}"),
            ):
                result = await self._runner.run(
                    CommandRequest(executable="git", arguments=arguments, cwd=base)
                )
                if result.returncode:
                    raise CliExecutionError("git " + arguments[0], result.returncode, result.stderr)

    async def ensure_repository(self, request: GhRepositoryCloneRequest) -> GhRepositoryCheckout:
        """Reuse a local checkout or clone it into its workspace using ``gh``."""
        destination = request.destination.expanduser().resolve()
        lock = self._clone_locks.setdefault(destination, asyncio.Lock())

        async with lock:
            if await asyncio.to_thread(_is_git_checkout, destination):
                return GhRepositoryCheckout(repo=request.repo, path=destination, cloned=False)

            if await asyncio.to_thread(destination.exists):
                raise WorkspacePathError(
                    f"workspace destination exists but is not a Git checkout: {destination}"
                )

            try:
                await asyncio.to_thread(
                    destination.parent.mkdir,
                    parents=True,
                    exist_ok=True,
                )
            except OSError as error:
                raise WorkspacePathError(
                    f"cannot create workspace directory {destination.parent}: {error}"
                ) from error
            result = await self._runner.run(
                CommandRequest(
                    executable="gh",
                    arguments=("repo", "clone", request.repo, str(destination)),
                    timeout=None,
                )
            )
            if result.returncode != 0:
                raise CliExecutionError("gh", result.returncode, result.stderr)
            if not await asyncio.to_thread(_is_git_checkout, destination):
                raise CliOutputError(
                    f"gh reported a successful clone, but no Git checkout was created at "
                    f"{destination}"
                )

            return GhRepositoryCheckout(repo=request.repo, path=destination, cloned=True)

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


def _is_git_checkout(path: Path) -> bool:
    return path.is_dir() and (path / ".git").exists()


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
