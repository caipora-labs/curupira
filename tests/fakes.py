"""Controlled native-process and checkout boundaries for behavioral tests."""

from pathlib import Path

from typing_extensions import override

from gh_dispatch.clients.gh import GhClient
from gh_dispatch.coding_agents import CodingAgentCliAdapter, SessionStartedCallback
from gh_dispatch.models import (
    CodingTaskRequest,
    GhIssue,
    GhIssueSearchRequest,
    GhPullRequest,
    GhPullRequestSearchRequest,
    GhRepositoryCheckout,
    GhRepositoryCloneRequest,
    ProcessResult,
)


class FakeGitHub(GhClient):
    """Return configured GitHub items and record checkout requests."""

    def __init__(
        self, *, issues: list[GhIssue] | None = None, pulls: list[GhPullRequest] | None = None
    ) -> None:
        super().__init__()
        self.issues = issues or []
        self.pulls = pulls or []
        self.checkouts: list[Path] = []

    @override
    async def list_issues(self, request: GhIssueSearchRequest) -> list[GhIssue]:
        return self.issues

    @override
    async def list_pull_requests(self, request: GhPullRequestSearchRequest) -> list[GhPullRequest]:
        return self.pulls

    @override
    async def ensure_repository(self, request: GhRepositoryCloneRequest) -> GhRepositoryCheckout:
        self.checkouts.append(request.destination)
        return GhRepositoryCheckout(repo=request.repo, path=request.destination, cloned=False)


class RecordingAdapter(CodingAgentCliAdapter):
    """Record native requests and emit a deterministic resumable session."""

    executable = "fake"
    provider = "opencode"

    def __init__(self, *, returncode: int = 0) -> None:
        super().__init__()
        self.requests: list[CodingTaskRequest] = []
        self.returncode = returncode

    @override
    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        return (request.message,)

    @override
    async def run_task(
        self,
        request: CodingTaskRequest,
        *,
        on_session_started: SessionStartedCallback | None = None,
    ) -> ProcessResult:
        self.requests.append(request)
        if on_session_started is not None:
            await on_session_started(request.session_id or "native-session")
        return ProcessResult(returncode=self.returncode, stdout="Completed")
