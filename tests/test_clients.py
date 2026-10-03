from __future__ import annotations

import asyncio
import json
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest

from gh_dispatch.clients.claude import ClaudeCodeClient
from gh_dispatch.clients.codex import CodexClient
from gh_dispatch.clients.cursor import CursorCliClient
from gh_dispatch.clients.gh import GhClient
from gh_dispatch.clients.opencode import OpenCodeClient
from gh_dispatch.clients.process import AsyncProcessRunner
from gh_dispatch.coding_agents import CodingAgent, create_coding_agent
from gh_dispatch.errors import (
    CliExecutionError,
    CliNotFoundError,
    CliOutputError,
    UnsupportedCodingAgentError,
    WorkspacePathError,
)
from gh_dispatch.models import (
    CodingTaskRequest,
    CommandRequest,
    GhIssueSearchRequest,
    GhPullRequestSearchRequest,
    GhRepositoryCloneRequest,
    ProcessResult,
)


class RecordingRunner(AsyncProcessRunner):
    def __init__(self, *results: ProcessResult) -> None:
        self.results = list(results)
        self.requests: list[CommandRequest] = []

    async def run(
        self,
        request: CommandRequest,
        *,
        on_stdout_line: Callable[[str], Awaitable[None]] | None = None,
    ) -> ProcessResult:
        self.requests.append(request)
        result = self.results.pop(0)
        if on_stdout_line is not None:
            for line in result.stdout.splitlines():
                await on_stdout_line(line)
        return result


class CloneCreatingRunner(AsyncProcessRunner):
    def __init__(self) -> None:
        self.requests: list[CommandRequest] = []

    async def run(
        self,
        request: CommandRequest,
        *,
        on_stdout_line: Callable[[str], Awaitable[None]] | None = None,
    ) -> ProcessResult:
        self.requests.append(request)
        await asyncio.sleep(0)
        destination = Path(request.arguments[-1])
        destination.mkdir(parents=True, exist_ok=True)
        (destination / ".git").mkdir()
        return ProcessResult(returncode=0)


@pytest.mark.parametrize(
    ("provider", "adapter"),
    [
        ("opencode", OpenCodeClient),
        ("codex", CodexClient),
        ("claude", ClaudeCodeClient),
        ("cursor", CursorCliClient),
    ],
)
def test_coding_agent_factory_creates_provider_adapter(
    provider: str,
    adapter: type[CodingAgent],
) -> None:
    coding_agent = create_coding_agent(provider)

    assert isinstance(coding_agent, CodingAgent)
    assert isinstance(coding_agent, adapter)


def test_coding_agent_factory_rejects_unsupported_provider() -> None:
    with pytest.raises(UnsupportedCodingAgentError, match="unsupported coding agent provider"):
        create_coding_agent("unsupported")


@pytest.mark.asyncio
async def test_gh_client_builds_argument_vector_and_validates_response() -> None:
    runner = RecordingRunner(
        ProcessResult(
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "number": 42,
                        "title": "Add tests",
                        "body": "Details",
                        "url": "https://github.com/acme/api/issues/42",
                        "state": "OPEN",
                        "labels": [{"name": "ready"}],
                    }
                ]
            ),
        )
    )
    gh = GhClient(runner)

    issues = await gh.list_issues(
        GhIssueSearchRequest(
            repo="acme/api",
            query='is:open label:"agent ready"; this is data',
        )
    )

    assert issues[0].number == 42
    assert issues[0].labels[0].name == "ready"
    assert runner.requests[0].arguments == (
        "issue",
        "list",
        "--repo",
        "acme/api",
        "--state",
        "open",
        "--search",
        'is:open label:"agent ready"; this is data',
        "--limit",
        "1",
        "--json",
        "number,title,body,url,state,labels",
    )


@pytest.mark.asyncio
async def test_gh_client_supports_project_item_jq_filters() -> None:
    filtered_issues = [
        {
            "number": number,
            "title": "Board task",
            "url": f"https://github.com/mariotaddeucci/bob/issues/{number}",
            "projectItems": [{"status": {"name": "Todo"}}],
        }
        for number in (8, 9)
    ]
    runner = RecordingRunner(
        ProcessResult(
            returncode=0,
            stdout="\n".join(json.dumps(issue) for issue in filtered_issues) + "\n",
        )
    )
    gh = GhClient(runner)

    issues = await gh.list_issues(
        GhIssueSearchRequest(
            repo="mariotaddeucci/bob",
            query="project:mariotaddeucci/5",
        )
    )

    assert [issue.number for issue in issues] == [8, 9]
    assert issues[0].state is None
    assert runner.requests[0].arguments == (
        "issue",
        "list",
        "--repo",
        "mariotaddeucci/bob",
        "--state",
        "open",
        "--search",
        "project:mariotaddeucci/5",
        "--limit",
        "1",
        "--json",
        "number,title,url,projectItems",
        "--jq",
        '.[] | select(any(.projectItems[]?; .status.name == "Todo"))',
    )


@pytest.mark.asyncio
async def test_gh_client_lists_pull_requests_with_typed_metadata() -> None:
    pull_request = {
        "number": 12,
        "title": "Add pull request watcher",
        "body": "Please review",
        "url": "https://github.com/acme/api/pull/12",
        "state": "OPEN",
        "labels": [],
        "isDraft": True,
        "headRefName": "feature/watcher",
        "baseRefName": "main",
    }
    runner = RecordingRunner(ProcessResult(returncode=0, stdout=json.dumps([pull_request])))
    pull_requests = await GhClient(runner).list_pull_requests(
        GhPullRequestSearchRequest(
            repo="acme/api",
            query="is:open label:review-needed",
            limit=10,
        )
    )

    assert pull_requests[0].number == 12
    assert pull_requests[0].is_draft is True
    assert pull_requests[0].head_ref_name == "feature/watcher"
    assert runner.requests[0].arguments == (
        "pr",
        "list",
        "--repo",
        "acme/api",
        "--state",
        "open",
        "--search",
        "is:open label:review-needed",
        "--limit",
        "10",
        "--json",
        "number,title,body,url,state,labels,isDraft,headRefName,baseRefName",
    )


@pytest.mark.asyncio
async def test_gh_client_raises_on_nonzero_exit() -> None:
    runner = RecordingRunner(ProcessResult(returncode=1, stderr="not authenticated"))
    gh = GhClient(runner)

    with pytest.raises(CliExecutionError, match="not authenticated"):
        await gh.list_issues(GhIssueSearchRequest(repo="acme/api", query="is:open"))
    assert len(runner.requests) == 1


@pytest.mark.asyncio
async def test_gh_client_retries_transient_failures_with_pyresilience() -> None:
    runner = RecordingRunner(
        ProcessResult(returncode=1, stderr="API rate limit exceeded (HTTP 429)"),
        ProcessResult(returncode=0, stdout="[]"),
    )
    gh = GhClient(runner)

    assert await gh.list_issues(GhIssueSearchRequest(repo="acme/api", query="is:open")) == []
    assert len(runner.requests) == 2


@pytest.mark.asyncio
async def test_gh_client_rejects_invalid_json() -> None:
    gh = GhClient(RecordingRunner(ProcessResult(returncode=0, stdout="not json")))

    with pytest.raises(CliOutputError, match="invalid issue JSON"):
        await gh.list_issues(GhIssueSearchRequest(repo="acme/api", query="is:open"))


@pytest.mark.asyncio
async def test_gh_client_clones_missing_repository_once_into_workspace(tmp_path: Path) -> None:
    runner = CloneCreatingRunner()
    gh = GhClient(runner)
    request = GhRepositoryCloneRequest(repo="acme/api", destination=tmp_path / "acme" / "api")

    first, second = await __import__("asyncio").gather(
        gh.ensure_repository(request),
        gh.ensure_repository(request),
    )

    assert first.path == request.destination
    assert first.cloned is True
    assert second.path == request.destination
    assert second.cloned is False
    assert (request.destination / ".git").is_dir()
    assert len(runner.requests) == 1
    assert runner.requests[0].arguments == (
        "repo",
        "clone",
        "acme/api",
        str(request.destination),
    )


@pytest.mark.asyncio
async def test_gh_client_reuses_existing_checkout_without_cloning(tmp_path: Path) -> None:
    destination = tmp_path / "acme" / "api"
    (destination / ".git").mkdir(parents=True)
    runner = CloneCreatingRunner()
    checkout = await GhClient(runner).ensure_repository(
        GhRepositoryCloneRequest(repo="acme/api", destination=destination)
    )

    assert checkout.path == destination
    assert checkout.cloned is False
    assert runner.requests == []


@pytest.mark.asyncio
async def test_gh_client_does_not_overwrite_non_git_workspace_path(tmp_path: Path) -> None:
    destination = tmp_path / "acme" / "api"
    destination.mkdir(parents=True)
    runner = CloneCreatingRunner()

    with pytest.raises(WorkspacePathError, match="not a Git checkout"):
        await GhClient(runner).ensure_repository(
            GhRepositoryCloneRequest(repo="acme/api", destination=destination)
        )

    assert runner.requests == []


@pytest.mark.asyncio
async def test_opencode_client_inherits_terminal_and_uses_repo_as_cwd(tmp_path: Path) -> None:
    runner = RecordingRunner(ProcessResult(returncode=0))
    opencode = OpenCodeClient(runner)

    await opencode.run_task(
        CodingTaskRequest(
            cwd=tmp_path,
            message="Solve issue 42",
            model="anthropic/claude-sonnet",
            agent="build",
            effort="high",
        )
    )

    request = runner.requests[0]
    assert request.executable == "opencode"
    assert request.arguments == (
        "run",
        "--format",
        "json",
        "--model",
        "anthropic/claude-sonnet",
        "--agent",
        "build",
        "--variant",
        "high",
        "Solve issue 42",
    )
    assert request.cwd == tmp_path
    assert request.capture_output is True
    assert request.timeout is None


@pytest.mark.asyncio
async def test_opencode_client_uses_default_profile_values_when_options_omitted(
    tmp_path: Path,
) -> None:
    runner = RecordingRunner(ProcessResult(returncode=0))
    opencode = OpenCodeClient(runner)

    await opencode.run_task(CodingTaskRequest(cwd=tmp_path, message="Solve issue 42"))

    assert runner.requests[0].arguments == ("run", "--format", "json", "Solve issue 42")


@pytest.mark.asyncio
async def test_opencode_client_reports_session_id_and_resumes_existing_session(
    tmp_path: Path,
) -> None:
    runner = RecordingRunner(
        ProcessResult(
            returncode=0,
            stdout=(
                '{"type":"step_start","sessionID":"ses_123"}\n'
                '{"type":"text","sessionID":"ses_123","part":{"text":"Done"}}\n'
            ),
        )
    )
    session_ids: list[str] = []

    async def session_started(session_id: str) -> None:
        session_ids.append(session_id)

    result = await OpenCodeClient(runner).run_task(
        CodingTaskRequest(
            cwd=tmp_path,
            message="Continue the task",
            session_id="ses_123",
        ),
        on_session_started=session_started,
    )

    assert session_ids == ["ses_123"]
    assert result.stdout == "Done"
    assert runner.requests[0].arguments == (
        "run",
        "--format",
        "json",
        "--session",
        "ses_123",
        "Continue the task",
    )


@pytest.mark.asyncio
async def test_codex_client_streams_session_id_and_resumes_by_thread_id(
    tmp_path: Path,
) -> None:
    runner = RecordingRunner(
        ProcessResult(
            returncode=0,
            stdout=(
                '{"type":"thread.started","thread_id":"thread_123"}\n'
                '{"type":"item.completed","item":{"type":"agent_message","text":"Done"}}\n'
            ),
        )
    )
    session_ids: list[str] = []

    async def session_started(session_id: str) -> None:
        session_ids.append(session_id)

    result = await CodexClient(runner).run_task(
        CodingTaskRequest(
            cwd=tmp_path,
            message="Continue the task",
            model="gpt-5.4",
            agent="local-coding-profile",
            effort="high",
            session_id="thread_123",
        ),
        on_session_started=session_started,
    )

    assert result.stdout == "Done"
    assert session_ids == ["thread_123"]
    assert runner.requests[0].executable == "codex"
    assert runner.requests[0].arguments == (
        "--profile",
        "local-coding-profile",
        "exec",
        "resume",
        "thread_123",
        "--json",
        "--model",
        "gpt-5.4",
        "--config",
        'model_reasoning_effort="high"',
        "Continue the task",
    )


@pytest.mark.asyncio
async def test_codex_client_maps_initial_profile_and_workspace_permissions(
    tmp_path: Path,
) -> None:
    runner = RecordingRunner(
        ProcessResult(
            returncode=0,
            stdout='{"type":"thread.started","thread_id":"thread_new"}\n',
        )
    )

    await CodexClient(runner).run_task(
        CodingTaskRequest(
            cwd=tmp_path,
            message="Implement the task",
            model="gpt-5.4",
            agent="local-coding-profile",
            effort="high",
        )
    )

    assert runner.requests[0].arguments == (
        "--profile",
        "local-coding-profile",
        "exec",
        "--json",
        "--sandbox",
        "workspace-write",
        "--approve-for-me",
        "--model",
        "gpt-5.4",
        "--config",
        'model_reasoning_effort="high"',
        "Implement the task",
    )


@pytest.mark.asyncio
async def test_claude_code_client_streams_and_resumes_session(tmp_path: Path) -> None:
    runner = RecordingRunner(
        ProcessResult(
            returncode=0,
            stdout=(
                '{"type":"system","subtype":"init","session_id":"claude-session"}\n'
                '{"type":"result","session_id":"claude-session","result":"Done"}\n'
            ),
        )
    )
    session_ids: list[str] = []

    async def session_started(session_id: str) -> None:
        session_ids.append(session_id)

    result = await ClaudeCodeClient(runner).run_task(
        CodingTaskRequest(
            cwd=tmp_path,
            message="Continue the task",
            model="sonnet",
            agent="reviewer",
            effort="high",
            session_id="claude-session",
        ),
        on_session_started=session_started,
    )

    assert result.stdout == "Done"
    assert session_ids == ["claude-session"]
    assert runner.requests[0].executable == "claude"
    assert runner.requests[0].arguments == (
        "-p",
        "Continue the task",
        "--resume",
        "claude-session",
        "--output-format",
        "stream-json",
        "--verbose",
        "--permission-mode",
        "auto",
        "--permission-prompts",
        "none",
        "--model",
        "sonnet",
        "--agent",
        "reviewer",
        "--effort",
        "high",
    )


@pytest.mark.asyncio
async def test_cursor_cli_client_uses_agent_cli_model_mode_and_resume(tmp_path: Path) -> None:
    runner = RecordingRunner(
        ProcessResult(
            returncode=0,
            stdout=(
                '{"type":"system","subtype":"init","session_id":"cursor-chat"}\n'
                '{"type":"result","result":"Done","session_id":"cursor-chat"}\n'
            ),
        )
    )
    session_ids: list[str] = []

    async def session_started(session_id: str) -> None:
        session_ids.append(session_id)

    result = await CursorCliClient(runner).run_task(
        CodingTaskRequest(
            cwd=tmp_path,
            message="Continue the task",
            model="composer-2",
            agent="plan",
            session_id="cursor-chat",
        ),
        on_session_started=session_started,
    )

    assert result.stdout == "Done"
    assert session_ids == ["cursor-chat"]
    assert runner.requests[0].executable == "agent"
    assert runner.requests[0].arguments == (
        "-p",
        "--force",
        "--trust",
        "--output-format",
        "stream-json",
        "--resume",
        "cursor-chat",
        "--model",
        "composer-2",
        "--mode",
        "plan",
        "Continue the task",
    )


@pytest.mark.asyncio
async def test_process_runner_passes_arguments_without_shell_interpretation() -> None:
    runner = AsyncProcessRunner()
    payload = "value; this must not run as shell"

    result = await runner.run(
        CommandRequest(
            executable=sys.executable,
            arguments=("-c", "import sys; print(sys.argv[1])", payload),
        )
    )

    assert result.returncode == 0
    assert result.stdout.strip() == payload


@pytest.mark.asyncio
async def test_process_runner_streams_stdout_lines_and_captures_output() -> None:
    lines: list[str] = []

    async def capture(line: str) -> None:
        lines.append(line)

    result = await AsyncProcessRunner().run(
        CommandRequest(
            executable=sys.executable,
            arguments=("-c", "print('first'); print('second')"),
        ),
        on_stdout_line=capture,
    )

    assert result.returncode == 0
    assert result.stdout == "first\nsecond\n"
    assert lines == ["first", "second"]


@pytest.mark.asyncio
async def test_process_runner_reports_missing_executable() -> None:
    with pytest.raises(CliNotFoundError):
        await AsyncProcessRunner().run(
            CommandRequest(executable="gh-dispatch-definitely-not-installed")
        )
