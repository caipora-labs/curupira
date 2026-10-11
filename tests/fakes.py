"""Controlled native-process and checkout boundaries for behavioral tests."""

from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from typing_extensions import override

from curupira.agents.base import CodingAgentCliAdapter, SessionStartedCallback
from curupira.clients.az import AzClient
from curupira.clients.github_graphql import GitHubGraphQLClient
from curupira.clients.process import AsyncProcessRunner
from curupira.models import (
    CodingTaskRequest,
    CommandRequest,
    GhIssue,
    GhPullRequest,
    GhTaskViewRequest,
    GitHubSearchRequest,
    ProcessResult,
)
from curupira.models.configuration import (
    IssueAutomationConfiguration,
    PullRequestAutomationConfiguration,
)
from curupira.vcs.base import Checkout, CheckoutRequest, VersionControl


class FakeVersionControl(VersionControl):
    """Record checkout lifecycle calls without invoking external Git commands."""

    def __init__(self) -> None:
        super().__init__()
        self.checkouts: list[Path] = []
        self.worktrees: list[Path] = []
        self.removed_worktrees: list[Path] = []
        self.setup_scripts: list[str] = []
        self.remotes: list[str] = []
        self.cloned = False

    @override
    async def clone(self, remote: str, destination: Path) -> None:
        raise AssertionError("fake checkout overrides ensure_checkout")

    @override
    async def ensure_checkout(self, request: CheckoutRequest) -> Checkout:
        self.checkouts.append(request.destination)
        self.remotes.append(request.remote)
        return Checkout(remote=request.remote, path=request.destination, cloned=self.cloned)

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
        self, checkout: Checkout, *, automation_id: str, task_type: str, task_id: str
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
        self, checkout: Checkout, *, automation_id: str, task_type: str, task_id: str
    ) -> None:
        self.removed_worktrees.extend(self.worktrees[-1:])


class FakeGitHub(GitHubGraphQLClient):
    """Return configured GitHub items without calling the GraphQL API."""

    def __init__(
        self, *, issues: list[GhIssue] | None = None, pulls: list[GhPullRequest] | None = None
    ) -> None:
        super().__init__()
        self.issues = issues or []
        self.pulls = pulls or []
        self.requests: list[GitHubSearchRequest] = []
        self.vcs = FakeVersionControl()

    @property
    def checkouts(self) -> list[Path]:
        return self.vcs.checkouts

    @property
    def worktrees(self) -> list[Path]:
        return self.vcs.worktrees

    @property
    def removed_worktrees(self) -> list[Path]:
        return self.vcs.removed_worktrees

    @property
    def setup_scripts(self) -> list[str]:
        return self.vcs.setup_scripts

    @override
    async def list_issues(
        self,
        request: GitHubSearchRequest,
        *,
        configuration: IssueAutomationConfiguration | None = None,
    ) -> list[GhIssue]:
        del configuration
        self.requests.append(request)
        return self.issues

    @override
    async def list_pull_requests(
        self,
        request: GitHubSearchRequest,
        *,
        configuration: PullRequestAutomationConfiguration | None = None,
    ) -> list[GhPullRequest]:
        del configuration
        self.requests.append(request)
        return self.pulls

    @override
    async def view_issue(self, request: GhTaskViewRequest) -> GhIssue:
        issue = next((item for item in self.issues if item.number == request.number), None)
        if issue is None:
            raise AssertionError(f"unexpected issue lookup: {request.repo}#{request.number}")
        return issue.model_copy(update={"state": issue.state or "OPEN"})

    @override
    async def view_pull_request(self, request: GhTaskViewRequest) -> GhPullRequest:
        pull = next((item for item in self.pulls if item.number == request.number), None)
        if pull is None:
            raise AssertionError(f"unexpected pull-request lookup: {request.repo}#{request.number}")
        return pull.model_copy(update={"state": pull.state or "OPEN"})

    @override
    async def list_pull_requests_for_issue(
        self, repo: str, issue_number: int
    ) -> list[GhPullRequest]:
        del repo, issue_number
        return self.pulls


def use_fake_github(monkeypatch: pytest.MonkeyPatch, fake: FakeGitHub) -> FakeGitHub:
    """Install ``fake`` as the GraphQL client constructed by built-in GitHub paths."""

    def factory(runner: AsyncProcessRunner | None = None) -> FakeGitHub:
        del runner
        return fake

    monkeypatch.setattr("curupira.providers.github.issues.GitHubGraphQLClient", factory)
    monkeypatch.setattr("curupira.providers.github.pull_requests.GitHubGraphQLClient", factory)
    monkeypatch.setattr("curupira.dispatcher.GitHubGraphQLClient", factory)
    monkeypatch.setattr("curupira.cli.GitHubGraphQLClient", factory)
    monkeypatch.setattr("curupira.config_reload.GitHubGraphQLClient", factory)
    return fake


def use_fake_azure(monkeypatch: pytest.MonkeyPatch, fake: AzClient) -> AzClient:
    """Install ``fake`` as the AzClient constructed by the Azure pull-request trigger."""
    monkeypatch.setattr("curupira.providers.azure.provider.AzClient", lambda runner=None: fake)
    return fake


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


class CallbackRunner(AsyncProcessRunner):
    """Await a callback in place of starting a process, then exit successfully."""

    def __init__(self, on_run: Callable[[], Awaitable[None]]) -> None:
        super().__init__()
        self.on_run = on_run

    @override
    async def run(
        self,
        request: CommandRequest,
        *,
        on_stdout_line: Callable[[str], Awaitable[None]] | None = None,
    ) -> ProcessResult:
        await self.on_run()
        return ProcessResult(returncode=0)


class AssigningAdapter(CodingAgentCliAdapter):
    """Use the shared run lifecycle with Curupira-assigned session identifiers."""

    executable = "fake"
    provider = "opencode"
    assigns_session_id = True

    def __init__(self, runner: AsyncProcessRunner) -> None:
        super().__init__(runner)
        self.requests: list[CodingTaskRequest] = []

    @override
    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        self.requests.append(request)
        return (request.message,)
