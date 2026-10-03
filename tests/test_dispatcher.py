from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest

from gh_dispatch.clients.gh import GhClient
from gh_dispatch.clients.opencode import OpenCodeClient
from gh_dispatch.clients.process import AsyncProcessRunner
from gh_dispatch.coding_agents import CodingAgent, SessionStartedCallback
from gh_dispatch.config import AppSettings
from gh_dispatch.dispatcher import (
    dispatch_next_issue,
    dispatch_next_pull_request,
    render_prompt,
)
from gh_dispatch.models import CodingTaskRequest, CommandRequest, ProcessResult, SelectedTask
from gh_dispatch.repositories import RunningSessionRepository


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
        if request.arguments[:2] == ("repo", "clone"):
            destination = Path(request.arguments[3])
            destination.mkdir(parents=True, exist_ok=True)
            (destination / ".git").mkdir()
            return ProcessResult(returncode=0)
        result = self.results.pop(0)
        if on_stdout_line is not None:
            for line in result.stdout.splitlines():
                await on_stdout_line(line)
        return result


class InterruptOnceAgent(CodingAgent):
    def __init__(self) -> None:
        super().__init__()
        self.requests: list[CodingTaskRequest] = []

    async def run_task(
        self,
        request: CodingTaskRequest,
        *,
        on_session_started: SessionStartedCallback | None = None,
    ) -> ProcessResult:
        self.requests.append(request)
        if request.session_id is None:
            assert on_session_started is not None
            await on_session_started("ses_dispatch")
            raise asyncio.CancelledError
        return ProcessResult(returncode=0)


def make_settings(first_path: Path, second_path: Path):
    return AppSettings.model_validate(
        {
            "core": {"max_active_tasks": 1},
            "agent": {
                "prompt": "${repo}#${issue_number}: ${issue_title}\n${issue_body}\n${issue_url}",
                "pull_request_prompt": (
                    "Review ${pull_request_number}: ${pull_request_title}\n"
                    "${pull_request_body}\n${pull_request_head_ref}->${pull_request_base_ref}"
                ),
            },
            "coding_agents": {
                "default": "opencode-default",
                "profiles": {
                    "opencode-default": {
                        "provider": "opencode",
                        "model": "openai/default-model",
                        "agent": "plan",
                        "effort": "medium",
                    },
                    "opencode-custom": {
                        "provider": "opencode",
                        "model": "anthropic/claude-sonnet",
                        "agent": "build",
                        "effort": "high",
                    },
                },
            },
            "watchers": {
                "issues": {
                    "poll_interval_seconds": 30,
                    "batch_size": 30,
                    "repositories": [
                        {
                            "repo": "acme/first",
                            "path": first_path,
                            "query": "is:open label:ready",
                        },
                        {
                            "repo": "acme/second",
                            "path": second_path,
                            "query": "is:open label:ready",
                            "prompt": "Custom prompt for ${issue_number}",
                            "coding_agent": "opencode-custom",
                        },
                    ],
                },
                "pull_requests": {
                    "repositories": [
                        {
                            "repo": "acme/prs",
                            "path": first_path.parent / "pr-checkout",
                            "query": "is:open label:review-needed",
                            "coding_agent": "opencode-default",
                        }
                    ]
                },
            },
        }
    )


def issue_json(number: int = 7) -> str:
    return json.dumps(
        [
            {
                "number": number,
                "title": "Implement dispatch",
                "body": "Issue details",
                "url": f"https://github.com/acme/second/issues/{number}",
                "state": "OPEN",
                "labels": [],
            }
        ]
    )


@pytest.mark.asyncio
async def test_dispatch_uses_first_repository_with_a_matching_issue(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path / "first", tmp_path / "second")
    gh_runner = RecordingRunner(
        ProcessResult(returncode=0, stdout="[]"),
        ProcessResult(returncode=0, stdout=issue_json()),
    )
    opencode_runner = RecordingRunner(ProcessResult(returncode=0))

    outcome = await dispatch_next_issue(
        settings,
        GhClient(gh_runner),
        dry_run=True,
    )

    assert outcome.selected is not None
    assert outcome.selected.repository.repo == "acme/second"
    assert outcome.selected.number == 7
    assert len(gh_runner.requests) == 2
    assert opencode_runner.requests == []


@pytest.mark.asyncio
async def test_dispatch_renders_repo_override_and_starts_opencode(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path / "first", tmp_path / "second")
    selected_issue = json.loads(issue_json())[0]
    selected = settings.watchers.issues.repositories[1]

    prompt = render_prompt(
        settings,
        SelectedTask(
            task_type="issue",
            repository=selected,
            number=selected_issue["number"],
            title=selected_issue["title"],
            body=selected_issue["body"],
            url=selected_issue["url"],
            workspace_path=selected.path or tmp_path / "second",
        ),
    )
    assert prompt == "Custom prompt for 7"

    assert settings.watchers.pull_requests is not None
    pull_request_repository = settings.watchers.pull_requests.repositories[0]
    pull_request_prompt = render_prompt(
        settings,
        SelectedTask(
            task_type="pull_request",
            repository=pull_request_repository,
            number=17,
            title="Update API",
            body="Please review",
            url="https://github.com/acme/prs/pull/17",
            workspace_path=pull_request_repository.workspace_path(settings.core.workspace_dir),
            is_draft=True,
            head_ref_name="feature/api",
            base_ref_name="main",
        ),
    )
    assert pull_request_prompt == "Review 17: Update API\nPlease review\nfeature/api->main"

    gh_runner = RecordingRunner(
        ProcessResult(returncode=0, stdout="[]"),
        ProcessResult(returncode=0, stdout=issue_json()),
    )
    opencode_runner = RecordingRunner(ProcessResult(returncode=0))
    outcome = await dispatch_next_issue(
        settings,
        GhClient(gh_runner),
        agent_factory=lambda _provider: OpenCodeClient(opencode_runner),
    )

    assert outcome.process is not None
    assert outcome.process.returncode == 0
    assert opencode_runner.requests[0].cwd == tmp_path / "second"
    assert opencode_runner.requests[0].arguments == (
        "run",
        "--format",
        "json",
        "--model",
        "anthropic/claude-sonnet",
        "--agent",
        "build",
        "--variant",
        "high",
        "Custom prompt for 7",
    )


@pytest.mark.asyncio
async def test_dispatch_can_start_a_pull_request_task(tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "first", tmp_path / "second")
    pull_request_json = json.dumps(
        [
            {
                "number": 17,
                "title": "Update API",
                "body": "Please review",
                "url": "https://github.com/acme/prs/pull/17",
                "state": "OPEN",
                "labels": [],
                "isDraft": True,
                "headRefName": "feature/api",
                "baseRefName": "main",
            }
        ]
    )
    gh_runner = RecordingRunner(ProcessResult(returncode=0, stdout=pull_request_json))
    opencode_runner = RecordingRunner(ProcessResult(returncode=0))

    outcome = await dispatch_next_pull_request(
        settings,
        GhClient(gh_runner),
        agent_factory=lambda _provider: OpenCodeClient(opencode_runner),
    )

    assert outcome.selected is not None
    assert outcome.selected.task_type == "pull_request"
    assert outcome.selected.number == 17
    assert opencode_runner.requests[0].cwd == tmp_path / "pr-checkout"
    assert opencode_runner.requests[0].arguments == (
        "run",
        "--format",
        "json",
        "--model",
        "openai/default-model",
        "--agent",
        "plan",
        "--variant",
        "medium",
        "Review 17: Update API\nPlease review\nfeature/api->main",
    )


@pytest.mark.asyncio
async def test_one_shot_dispatch_persists_and_resumes_session(tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "first", tmp_path / "second")
    persisted = RunningSessionRepository(tmp_path / "state.sqlite3")
    agent = InterruptOnceAgent()

    def github() -> GhClient:
        return GhClient(
            RecordingRunner(
                ProcessResult(returncode=0, stdout="[]"),
                ProcessResult(returncode=0, stdout=issue_json()),
            )
        )

    with pytest.raises(asyncio.CancelledError):
        await dispatch_next_issue(
            settings,
            github(),
            agent_factory=lambda _provider: agent,
            session_repository=persisted,
        )

    saved = await persisted.list_all()
    assert len(saved) == 1
    assert saved[0].session_id == "ses_dispatch"

    outcome = await dispatch_next_issue(
        settings,
        github(),
        agent_factory=lambda _provider: agent,
        session_repository=persisted,
    )

    assert outcome.process is not None
    assert agent.requests[1].session_id == "ses_dispatch"
    assert "Continue the interrupted task" in agent.requests[1].message
    assert await persisted.list_all() == []


@pytest.mark.asyncio
async def test_dispatch_returns_empty_outcome_when_no_issues_match(tmp_path: Path) -> None:
    settings = make_settings(tmp_path / "first", tmp_path / "second")
    gh_runner = RecordingRunner(
        ProcessResult(returncode=0, stdout="[]"),
        ProcessResult(returncode=0, stdout="[]"),
    )
    opencode_runner = RecordingRunner()

    outcome = await dispatch_next_issue(
        settings,
        GhClient(gh_runner),
    )

    assert outcome.selected is None
    assert outcome.process is None
    assert opencode_runner.requests == []
