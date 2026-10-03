from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest

from gh_dispatch.clients.gh import GhClient
from gh_dispatch.coding_agents import CodingAgent
from gh_dispatch.config import AppSettings
from gh_dispatch.models import (
    CodingAgentProfile,
    CodingAgentsSettings,
    CodingTaskRequest,
    CronJobSettings,
    GhRepositoryCheckout,
    GhRepositoryCloneRequest,
    ProcessResult,
    SelectedTask,
)
from gh_dispatch.repositories import CronScheduleRepository, RunningSessionRepository
from gh_dispatch.scheduler import CoreScheduler


class SlowCodingAgent(CodingAgent):
    def __init__(self) -> None:
        super().__init__()
        self.active = 0
        self.peak_active = 0
        self.requests: list[CodingTaskRequest] = []

    async def run_task(
        self,
        request: CodingTaskRequest,
        *,
        on_session_started: Callable[[str], Awaitable[None]] | None = None,
    ) -> ProcessResult:
        self.requests.append(request)
        if on_session_started is not None:
            await on_session_started(f"session-{len(self.requests)}")
        self.active += 1
        self.peak_active = max(self.peak_active, self.active)
        await asyncio.sleep(0.01)
        self.active -= 1
        return ProcessResult(returncode=0)


class ExistingWorkspaceGhClient(GhClient):
    def __init__(self) -> None:
        super().__init__()
        self.clone_requests: list[GhRepositoryCloneRequest] = []

    async def ensure_repository(self, request: GhRepositoryCloneRequest) -> GhRepositoryCheckout:
        self.clone_requests.append(request)
        return GhRepositoryCheckout(repo=request.repo, path=request.destination, cloned=False)


def make_settings(tmp_path: Path, max_active_tasks: int) -> AppSettings:
    return AppSettings.model_validate(
        {
            "core": {
                "max_active_tasks": max_active_tasks,
                "state_db_path": tmp_path / "state.sqlite3",
            },
            "agent": {"prompt": "Fix ${issue_number}: ${issue_title}"},
            "watchers": {
                "issues": {
                    "repositories": [
                        {
                            "repo": "acme/api",
                            "path": tmp_path,
                            "query": "is:open",
                        }
                    ]
                }
            },
        }
    )


def issue(number: int, path: Path) -> SelectedTask:
    from gh_dispatch.models import GhIssue, RepositorySettings

    repository = RepositorySettings(repo="acme/api", path=path, query="is:open")
    gh_issue = GhIssue(
        number=number,
        title=f"Task {number}",
        body="details",
        url=f"https://github.com/acme/api/issues/{number}",
        state="OPEN",
    )
    return SelectedTask(
        task_type="issue",
        repository=repository,
        number=gh_issue.number,
        title=gh_issue.title,
        body=gh_issue.body,
        url=gh_issue.url,
        workspace_path=path,
    )


async def issue_stream(issues: list[SelectedTask]) -> AsyncIterator[SelectedTask]:
    for selected in issues:
        yield selected


@pytest.mark.asyncio
async def test_scheduler_never_exceeds_configured_active_task_limit(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, max_active_tasks=2)
    gh = ExistingWorkspaceGhClient()
    opencode = SlowCodingAgent()
    scheduler = CoreScheduler(
        settings.core,
        settings.agent,
        settings.coding_agents,
        gh,
        RunningSessionRepository(settings.core.state_db_path),
        agent_factory=lambda _provider: opencode,
    )

    await scheduler.run(issue_stream([issue(number, tmp_path) for number in range(1, 7)]))

    assert opencode.peak_active == 2
    assert len(opencode.requests) == 6
    assert all(request.cwd == tmp_path for request in opencode.requests)
    assert len(gh.clone_requests) == 6


class InterruptibleCodingAgent(CodingAgent):
    def __init__(self) -> None:
        super().__init__()
        self.started = asyncio.Event()

    async def run_task(
        self,
        request: CodingTaskRequest,
        *,
        on_session_started: Callable[[str], Awaitable[None]] | None = None,
    ) -> ProcessResult:
        if on_session_started is not None:
            await on_session_started(request.session_id or "session-recover-me")
        self.started.set()
        await asyncio.Event().wait()
        return ProcessResult(returncode=0)


class CompletingCodingAgent(CodingAgent):
    def __init__(self) -> None:
        super().__init__()
        self.request: CodingTaskRequest | None = None

    async def run_task(
        self,
        request: CodingTaskRequest,
        *,
        on_session_started: Callable[[str], Awaitable[None]] | None = None,
    ) -> ProcessResult:
        self.request = request
        if on_session_started is not None and request.session_id is not None:
            await on_session_started(request.session_id)
        return ProcessResult(returncode=0)


@pytest.mark.asyncio
async def test_scheduler_recovers_persisted_session_after_cancellation(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, max_active_tasks=1)
    settings = settings.model_copy(
        update={
            "coding_agents": CodingAgentsSettings(
                default="codex-profile",
                profiles={
                    "codex-profile": CodingAgentProfile(
                        provider="codex",
                        model="gpt-5.4",
                        agent="local-profile",
                        effort="high",
                    )
                },
            )
        }
    )
    gh = ExistingWorkspaceGhClient()
    repository = RunningSessionRepository(settings.core.state_db_path)
    selected = issue(42, tmp_path)
    selected = selected.model_copy(
        update={
            "repository": selected.repository.model_copy(update={"coding_agent": "codex-profile"})
        }
    )
    interrupted_agent = InterruptibleCodingAgent()
    scheduler = CoreScheduler(
        settings.core,
        settings.agent,
        settings.coding_agents,
        gh,
        repository,
        agent_factory=lambda _provider: interrupted_agent,
    )

    running = asyncio.create_task(scheduler.run(issue_stream([selected])))
    await asyncio.wait_for(interrupted_agent.started.wait(), timeout=2)
    running.cancel()
    with pytest.raises(asyncio.CancelledError):
        await running

    saved_sessions = await repository.list_all()
    assert len(saved_sessions) == 1
    assert saved_sessions[0].session_id == "session-recover-me"
    assert saved_sessions[0].task.number == 42

    completing_agent = CompletingCodingAgent()
    recovery_scheduler = CoreScheduler(
        settings.core,
        settings.agent,
        settings.coding_agents,
        gh,
        repository,
        agent_factory=lambda _provider: completing_agent,
    )
    await recovery_scheduler.run(issue_stream([]), resume_sessions=saved_sessions)

    assert completing_agent.request is not None
    assert completing_agent.request.session_id == "session-recover-me"
    assert "Continue the interrupted task" in completing_agent.request.message
    assert completing_agent.request.model == "gpt-5.4"
    assert completing_agent.request.agent == "local-profile"
    assert completing_agent.request.effort == "high"
    assert await repository.list_all() == []


@pytest.mark.asyncio
async def test_scheduler_runs_cron_task_and_completes_persisted_occurrence(
    tmp_path: Path,
) -> None:
    settings = make_settings(tmp_path, max_active_tasks=1)
    database_path = settings.core.state_db_path
    session_repository = RunningSessionRepository(database_path)
    cron_repository = CronScheduleRepository(database_path)
    cron_job = CronJobSettings(
        id="daily-maintenance",
        schedule="0 9 * * *",
        repo="acme/api",
        prompt="Maintain ${repo} at ${task_number}",
    )
    scheduled_for = datetime(2026, 10, 3, 9, 0, tzinfo=UTC)
    await cron_repository.get_or_create(cron_job.id, scheduled_for)
    await cron_repository.set_pending(cron_job.id, scheduled_for)
    selected = SelectedTask(
        task_type="cron",
        repository=cron_job.repository_settings(),
        number=int(scheduled_for.timestamp()),
        title=cron_job.id,
        url=f"cron://{cron_job.id}",
        workspace_path=cron_job.workspace_path(tmp_path),
        cron_job_id=cron_job.id,
        scheduled_for=scheduled_for,
    )
    agent = SlowCodingAgent()
    scheduler = CoreScheduler(
        settings.core,
        settings.agent,
        settings.coding_agents,
        ExistingWorkspaceGhClient(),
        session_repository,
        cron_repository=cron_repository,
        agent_factory=lambda _provider: agent,
    )

    await scheduler.run(issue_stream([selected]))

    state = await cron_repository.state(cron_job.id)
    assert state is not None
    assert state.last_execution_at is not None
    assert state.pending_scheduled_for is None
    assert agent.requests[0].message == f"Maintain acme/api at {int(scheduled_for.timestamp())}"
    assert await session_repository.list_all() == []
