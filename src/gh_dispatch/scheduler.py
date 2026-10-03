"""Bounded asynchronous task scheduler for issue watcher results."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime

from gh_dispatch.clients.gh import GhClient
from gh_dispatch.coding_agents import (
    RESUME_SESSION_PROMPT,
    CodingAgent,
    CodingAgentFactory,
    create_coding_agent,
    resolve_coding_agent_profile,
)
from gh_dispatch.dispatcher import render_task_prompt
from gh_dispatch.errors import DispatchError
from gh_dispatch.models import (
    AgentSettings,
    CodingAgentsSettings,
    CodingTaskRequest,
    CoreSettings,
    GhRepositoryCloneRequest,
    RunningCodingSession,
    SelectedTask,
)
from gh_dispatch.repositories import CronScheduleRepository, RunningSessionRepository

logger = logging.getLogger(__name__)


class CoreScheduler:
    """Run no more than ``max_active_tasks`` coding-agent processes concurrently."""

    def __init__(
        self,
        core_settings: CoreSettings,
        agent_settings: AgentSettings,
        coding_agents_settings: CodingAgentsSettings,
        gh: GhClient,
        session_repository: RunningSessionRepository,
        cron_repository: CronScheduleRepository | None = None,
        agent_factory: CodingAgentFactory = create_coding_agent,
    ) -> None:
        self._core_settings = core_settings
        self._agent_settings = agent_settings
        self._coding_agents_settings = coding_agents_settings
        self._gh = gh
        self._session_repository = session_repository
        self._cron_repository = cron_repository
        self._agent_factory = agent_factory
        self._coding_agents: dict[str, CodingAgent] = {}

    async def run(
        self,
        tasks: AsyncIterator[SelectedTask],
        *,
        resume_sessions: Sequence[RunningCodingSession] = (),
    ) -> None:
        active: set[asyncio.Task[None]] = set()
        scheduled_ids: set[str] = set()

        async def schedule(
            selected: SelectedTask,
            session: RunningCodingSession | None = None,
        ) -> None:
            while len(active) >= self._core_settings.max_active_tasks:
                finished, _ = await asyncio.wait(active, return_when=asyncio.FIRST_COMPLETED)
                self._observe_finished(finished)
                active.difference_update(finished)
            task = asyncio.create_task(
                self._execute(selected, session),
                name=f"{selected.repository.repo}#{selected.number}",
            )
            active.add(task)

        try:
            for session in resume_sessions:
                record_id = _task_key(session.task)
                if record_id in scheduled_ids:
                    continue
                scheduled_ids.add(record_id)
                await schedule(session.task, session)

            async for selected in tasks:
                self._reap_finished(active)
                record_id = _task_key(selected)
                if record_id in scheduled_ids:
                    continue
                scheduled_ids.add(record_id)
                await schedule(selected)

            while active:
                finished, _ = await asyncio.wait(active, return_when=asyncio.FIRST_COMPLETED)
                self._observe_finished(finished)
                active.difference_update(finished)
        except BaseException:
            for task in active:
                task.cancel()
            await asyncio.gather(*active, return_exceptions=True)
            raise

    async def _execute(
        self,
        selected: SelectedTask,
        resumed_session: RunningCodingSession | None = None,
    ) -> None:
        repo = selected.repository.repo
        task_id = f"{repo}#{selected.number}"
        if resumed_session is None:
            logger.info("Starting %s %s: %s", selected.task_type, task_id, selected.title)
        else:
            logger.info(
                "Resuming %s %s in %s session %s",
                selected.task_type,
                task_id,
                resumed_session.provider,
                resumed_session.session_id,
            )

        process_finished = False
        try:
            if resumed_session is None:
                profile = resolve_coding_agent_profile(
                    self._coding_agents_settings,
                    selected.repository.coding_agent,
                )
                message = render_task_prompt(self._agent_settings, selected)
                session_id = None
                assert profile is not None
                provider = profile.provider
            else:
                profile = None
                message = RESUME_SESSION_PROMPT
                session_id = resumed_session.session_id
                provider = resumed_session.provider

            coding_agent = self._coding_agents.get(provider)
            if coding_agent is None:
                coding_agent = self._agent_factory(provider)
                self._coding_agents[provider] = coding_agent

            checkout = await self._gh.ensure_repository(
                GhRepositoryCloneRequest(
                    repo=repo,
                    destination=selected.workspace_path,
                )
            )
            if resumed_session is None:
                assert profile is not None
                model, agent, effort = profile.model, profile.agent, profile.effort
                stored_message = message
            else:
                model = resumed_session.model
                agent = resumed_session.agent
                effort = resumed_session.effort
                stored_message = resumed_session.message

            async def persist_session(session_id: str) -> None:
                await self._session_repository.save(
                    RunningCodingSession(
                        task=selected,
                        session_id=session_id,
                        message=stored_message,
                        provider=provider,
                        model=model,
                        agent=agent,
                        effort=effort,
                    )
                )

            if selected.task_type == "cron" and selected.cron_job_id is not None:
                if self._cron_repository is None:
                    raise DispatchError("cron task dispatched without a cron state repository")
                await self._cron_repository.mark_started(
                    selected.cron_job_id,
                    datetime.now(UTC),
                )

            result = await coding_agent.run_task(
                CodingTaskRequest(
                    cwd=checkout.path,
                    message=message,
                    model=model,
                    agent=agent,
                    effort=effort,
                    session_id=session_id,
                ),
                on_session_started=persist_session,
            )
            process_finished = True
        except asyncio.CancelledError:
            raise
        except DispatchError as error:
            logger.error("Task %s failed: %s", task_id, error)
            return
        except Exception:
            logger.exception("Unexpected failure while running %s", task_id)
            return
        finally:
            if process_finished:
                if selected.task_type == "cron" and selected.cron_job_id is not None:
                    if self._cron_repository is not None:
                        try:
                            await self._cron_repository.complete_run(
                                selected.cron_job_id,
                                selected,
                                self._session_repository,
                            )
                        except Exception:
                            logger.exception(
                                "Could not finalize cron occurrence for %s",
                                selected.cron_job_id,
                            )
                else:
                    try:
                        await self._session_repository.delete(selected)
                    except Exception:
                        logger.exception("Could not clear completed session state for %s", task_id)

        if result.returncode == 0:
            logger.info("Task %s finished successfully", task_id)
            if result.stdout.strip():
                logger.info("Coding-agent output for %s:\n%s", task_id, result.stdout.rstrip())
            return

        logger.error("Task %s exited with status %s", task_id, result.returncode)
        if result.stderr.strip():
            logger.error("Coding-agent error for %s:\n%s", task_id, result.stderr.rstrip())

    @staticmethod
    def _reap_finished(active: set[asyncio.Task[None]]) -> None:
        finished = {task for task in active if task.done()}
        CoreScheduler._observe_finished(finished)
        active.difference_update(finished)

    @staticmethod
    def _observe_finished(finished: set[asyncio.Task[None]]) -> None:
        for task in finished:
            if task.cancelled():
                continue
            error = task.exception()
            if error is not None:
                logger.error("Task worker failed: %s", error)


def _task_key(task: SelectedTask) -> str:
    if task.task_type == "cron":
        return f"{task.repository.repo}:cron:{task.cron_job_id}:{task.number}"
    return f"{task.repository.repo}:{task.task_type}:{task.number}"
