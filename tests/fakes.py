"""Controlled native-process and checkout boundaries for behavioral tests."""

from pathlib import Path

from typing_extensions import override

from opscli.agents.base import CodingAgentCliAdapter, SessionStartedCallback
from opscli.clients.gh import GhClient
from opscli.models import (
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
        self.worktrees: list[Path] = []
        self.removed_worktrees: list[Path] = []
        self.setup_scripts: list[str] = []

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

    @override
    async def run_setup_script(
        self,
        checkout: GhRepositoryCheckout,
        script: str,
        *,
        timeout_seconds: float | None = None,
        max_output_bytes: int = 1_000_000,
    ) -> ProcessResult:
        self.setup_scripts.append(script)
        return await super().run_setup_script(
            checkout,
            script,
            timeout_seconds=timeout_seconds,
            max_output_bytes=max_output_bytes,
        )

    @override
    async def ensure_worktree(
        self, checkout: GhRepositoryCheckout, *, automation_id: str, task_type: str, task_id: str
    ) -> Path:
        path = (
            checkout.path.with_name(f"{checkout.path.name}.worktrees")
            / automation_id
            / f"{task_type}-{task_id}"
        )
        self.worktrees.append(path)
        return path

    @override
    async def remove_worktree(
        self, checkout: GhRepositoryCheckout, *, automation_id: str, task_type: str, task_id: str
    ) -> None:
        self.removed_worktrees.append(
            checkout.path.with_name(f"{checkout.path.name}.worktrees")
            / automation_id
            / f"{task_type}-{task_id}"
        )


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
