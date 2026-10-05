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
    ProcessResult,
)
from gh_dispatch.vcs import Checkout, CheckoutRequest, VersionControl


class FakeGitHub(GhClient):
    """Return configured GitHub items and record checkout requests."""

    def __init__(
        self, *, issues: list[GhIssue] | None = None, pulls: list[GhPullRequest] | None = None
    ) -> None:
        super().__init__()
        self.issues = issues or []
        self.pulls = pulls or []
        self.vcs = FakeVersionControl()
        self.checkouts = self.vcs.checkouts
        self.worktrees = self.vcs.worktrees
        self.removed_worktrees = self.vcs.removed_worktrees
        self.setup_scripts = self.vcs.setup_scripts

    @override
    async def list_issues(self, request: GhIssueSearchRequest) -> list[GhIssue]:
        return self.issues

    @override
    async def list_pull_requests(self, request: GhPullRequestSearchRequest) -> list[GhPullRequest]:
        return self.pulls


class FakeVersionControl(VersionControl):
    """Record version-control operations without invoking external tools."""

    def __init__(self) -> None:
        super().__init__()
        self.checkouts: list[Path] = []
        self.worktrees: list[Path] = []
        self.removed_worktrees: list[Path] = []
        self.setup_scripts: list[str] = []

    @override
    async def clone(self, repo: str, destination: Path) -> None:
        destination.mkdir(parents=True)
        (destination / ".git").mkdir()

    @override
    async def ensure_checkout(self, request: CheckoutRequest) -> Checkout:
        self.checkouts.append(request.destination)
        return Checkout(repo=request.repo, path=request.destination, cloned=False)

    @override
    async def run_setup_script(
        self,
        checkout: Checkout,
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
        self, checkout: Checkout, *, automation_id: str, task_type: str, number: int
    ) -> Path:
        path = (
            checkout.path.with_name(f"{checkout.path.name}.worktrees")
            / automation_id
            / f"{task_type}-{number}"
        )
        self.worktrees.append(path)
        return path

    @override
    async def remove_worktree(
        self, checkout: Checkout, *, automation_id: str, task_type: str, number: int
    ) -> None:
        self.removed_worktrees.append(
            checkout.path.with_name(f"{checkout.path.name}.worktrees")
            / automation_id
            / f"{task_type}-{number}"
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
