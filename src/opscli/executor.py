"""The shared checkout, prompt, execution, and persistence lifecycle."""

import logging
from asyncio import CancelledError
from datetime import UTC, datetime
from string import Template

from opscli.clients.gh import GhClient
from opscli.coding_agents import (
    RESUME_SESSION_PROMPT,
    CliAdapterFactory,
    CodingAgentCliAdapter,
    create_cli_adapter,
)
from opscli.errors import PromptRenderError
from opscli.models import (
    CodingTaskRequest,
    ExecutionSettings,
    GhRepositoryCloneRequest,
    ProcessResult,
    RunningCodingSession,
    Task,
)
from opscli.repositories import CronScheduleRepository, RunningSessionRepository
from opscli.telemetry import TaskTelemetry

logger = logging.getLogger(__name__)


def render_task_prompt(task: Task) -> str:
    """Render only the task's own template using common and source-specific fields."""
    identity = task.identity
    context: dict[str, str] = {
        "repo": identity.repo,
        "automation_id": identity.automation_id,
        "task_type": identity.task_type,
        "task_number": str(identity.number),
        "task_title": task.title,
        "task_body": task.body or "",
        "task_url": task.url,
    }
    if identity.task_type in {"issue", "pull_request"}:
        for suffix in ("number", "title", "body", "url"):
            context[f"{identity.task_type}_{suffix}"] = context[f"task_{suffix}"]
    if identity.task_type == "pull_request":
        context.update(
            pull_request_is_draft=str(task.is_draft).lower() if task.is_draft is not None else "",
            pull_request_head_ref=task.head_ref_name or "",
            pull_request_base_ref=task.base_ref_name or "",
        )
    try:
        return Template(task.automation.configuration.prompt).substitute(context)
    except (KeyError, ValueError) as error:
        raise PromptRenderError(
            f"could not render prompt for {identity.automation_id}: {error}"
        ) from error


class TaskExecutor:
    """Execute new or resumed tasks with identical provider and state semantics."""

    def __init__(
        self,
        settings: ExecutionSettings,
        gh: GhClient,
        sessions: RunningSessionRepository,
        cron: CronScheduleRepository,
        *,
        adapter_factory: CliAdapterFactory = create_cli_adapter,
        telemetry: TaskTelemetry | None = None,
    ) -> None:
        self._settings = settings
        self._gh = gh
        self._sessions = sessions
        self._cron = cron
        self._adapter_factory = adapter_factory
        self._telemetry = telemetry or TaskTelemetry()
        self._adapters: dict[str, CodingAgentCliAdapter] = {}

    async def execute(
        self, task: Task, resumed: RunningCodingSession | None = None
    ) -> ProcessResult:
        """Execute one task within an outcome span."""
        identity = task.identity
        context = (identity.repo, identity.task_type, identity.number)
        action = "Resuming" if resumed is not None else "Starting"
        logger.info("%s task repo=%s type=%s id=%s", action, *context)
        try:
            with self._telemetry.task_span(task) as span:
                result = await self._execute_task(task, resumed)
                self._telemetry.record_result(span, result)
        except CancelledError:
            logger.warning("Cancelled task repo=%s type=%s id=%s", *context)
            raise
        except Exception as error:
            logger.exception(
                "Failed task repo=%s type=%s id=%s result=failure error=%s",
                *context,
                str(error) or type(error).__name__,
            )
            raise

        if result.returncode == 0:
            logger.info("Completed task repo=%s type=%s id=%s result=success", *context)
        else:
            message = result.stderr.strip() or f"process exited with status {result.returncode}"
            logger.error(
                "Failed task repo=%s type=%s id=%s result=failure error=%s",
                *context,
                message,
            )
        return result

    async def _execute_task(
        self, task: Task, resumed: RunningCodingSession | None = None
    ) -> ProcessResult:
        """Persist session events and remove state only after the native process exits."""
        if resumed is not None and resumed.task != task:
            raise ValueError("resumption must use the original persisted task snapshot")
        profile = task.automation.profile
        provider = profile.provider
        adapter = self._adapters.get(provider)
        if adapter is None:
            adapter = self._adapter_factory(provider)
            self._adapters[provider] = adapter
        checkout = await self._gh.ensure_repository(
            GhRepositoryCloneRequest(
                repo=task.identity.repo, destination=task.automation.workspace_path
            )
        )
        setup_script = task.automation.configuration.setup_script
        if checkout.cloned and setup_script is not None:
            result = await self._gh.run_setup_script(
                checkout,
                setup_script,
                timeout_seconds=self._settings.task_timeout_seconds,
                max_output_bytes=self._settings.max_output_bytes,
            )
            if result.returncode:
                logger.error(
                    "Setup script failed path=%s code=%s stderr=%s",
                    setup_script,
                    result.returncode,
                    result.stderr,
                )
                return result
        original_message = resumed.message if resumed is not None else render_task_prompt(task)

        async def persist(session_id: str) -> None:
            await self._sessions.save(
                RunningCodingSession(task=task, session_id=session_id, message=original_message)
            )

        if task.identity.task_type == "cron":
            await self._cron.mark_started(task.identity.automation_id, datetime.now(UTC))
        is_worktree = task.automation.configuration.checkout == "worktree"
        cwd = checkout.path
        if is_worktree:
            cwd = await self._gh.ensure_worktree(
                checkout,
                automation_id=task.identity.automation_id,
                task_type=task.identity.task_type,
                number=task.identity.number,
            )
        try:
            result = await adapter.run_task(
                CodingTaskRequest(
                    cwd=cwd,
                    profile=profile,
                    message=RESUME_SESSION_PROMPT if resumed is not None else original_message,
                    session_id=resumed.session_id if resumed is not None else None,
                    timeout=self._settings.task_timeout_seconds,
                    max_output_bytes=self._settings.max_output_bytes,
                ),
                on_session_started=persist,
            )
            if task.identity.task_type == "cron":
                await self._cron.complete_run(task, self._sessions)
            else:
                await self._sessions.delete(task)
            return result
        finally:
            if is_worktree:
                try:
                    await self._gh.remove_worktree(
                        checkout,
                        automation_id=task.identity.automation_id,
                        task_type=task.identity.task_type,
                        number=task.identity.number,
                    )
                except Exception:
                    logger.exception("Could not clean up worktree for %s", task.identity.key)
