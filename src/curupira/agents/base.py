"""Behavioral interface for external coding-agent CLI adapters."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import ClassVar
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError

from curupira.clients.process import AsyncProcessRunner
from curupira.errors import UnsupportedCodingAgentError
from curupira.models import CliProfileBase, CodingTaskRequest, CommandRequest, ProcessResult
from curupira.tasks.base import PLUGIN_API_VERSION

SessionStartedCallback = Callable[[str], Awaitable[None]]
RESUME_SESSION_PROMPT = (
    "Continue the interrupted task from this session. Review the existing conversation and "
    "repository state, then complete the requested work without repeating completed steps."
)


class EventText(BaseModel):
    """Text nested inside provider-native events."""

    model_config = ConfigDict(extra="ignore")
    text: str = ""
    type: str = ""


class CliEvent(BaseModel):
    """Relevant fields in OpenCode, Codex, Claude, and Cursor JSONL events."""

    model_config = ConfigDict(extra="ignore")
    type: str = ""
    session_id: str | None = Field(
        default=None, validation_alias=AliasChoices("sessionID", "session_id", "thread_id")
    )
    part: EventText | None = None
    item: EventText | None = None
    result: str | None = None


def parse_event(line: str) -> CliEvent | None:
    """Validate external JSON events, ignoring non-event output."""
    try:
        return CliEvent.model_validate_json(line)
    except ValidationError:
        return None


class CodingAgentCliAdapter(ABC):
    """Invoke a native CLI; agent definitions are owned by that external tool.

    Attributes:
        executable: Native CLI executable started for each task.
        provider: Value of ``provider`` in the TOML profile that selects this adapter.
        profile_model: Pydantic model validating this provider's profile table.
        display_name: Human-readable provider name shown in the dashboard.
        install_url: Where users install or learn about the native CLI.
        api_version: Plugin API version the implementation was written against.
        assigns_session_id: When ``True``, Curupira generates a UUID for each new run,
            reports it before the process starts, and passes it to ``build_arguments``
            as ``request.new_session_id``. Use it for CLIs that accept a caller-chosen
            session identifier instead of printing their own.
        auto_model: Value to pass as the model when the user wants the CLI's own
            automatic model selection, or ``None`` if the CLI has no documented native
            auto.
    """

    executable: ClassVar[str]
    provider: ClassVar[str]
    profile_model: ClassVar[type[CliProfileBase]]
    display_name: ClassVar[str]
    install_url: ClassVar[str]
    api_version: ClassVar[int] = PLUGIN_API_VERSION
    assigns_session_id: ClassVar[bool] = False
    auto_model: ClassVar[str | None] = None

    def __init__(self, runner: AsyncProcessRunner | None = None) -> None:
        self._runner = runner or AsyncProcessRunner()

    @abstractmethod
    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        """Translate a validated profile into native CLI arguments."""

    def session_id_from_line(self, line: str) -> str | None:
        """Return the native session identifier announced by one stdout line, if any.

        The default reads ``sessionID``, ``session_id``, or ``thread_id`` from a JSON
        event. Override it for CLIs that report their session in another shape. Each
        distinct identifier is reported once per run, however often it repeats.

        Args:
            line: One line of the CLI's standard output.

        Returns:
            The session identifier, or ``None`` when the line does not announce one.
        """
        event = parse_event(line)
        return event.session_id if event is not None else None

    async def run_task(
        self,
        request: CodingTaskRequest,
        *,
        on_session_started: SessionStartedCallback | None = None,
    ) -> ProcessResult:
        """Run headlessly and report native session identifiers while streaming.

        Adapters with ``assigns_session_id`` get a fresh UUID on new runs; it is reported
        through ``on_session_started`` before the process starts, so it is persisted even
        if the process dies early.
        """
        if request.profile.provider != self.provider:
            raise UnsupportedCodingAgentError(
                f"{self.provider} adapter cannot use {request.profile.provider} profile"
            )
        reported: set[str] = set()

        async def report(session_id: str) -> None:
            reported.add(session_id)
            if on_session_started is not None:
                await on_session_started(session_id)

        if self.assigns_session_id and request.session_id is None:
            new_session_id = str(uuid4())
            await report(new_session_id)
            request = request.model_copy(update={"new_session_id": new_session_id})

        async def handle(line: str) -> None:
            session_id = self.session_id_from_line(line)
            if session_id and session_id not in reported:
                await report(session_id)

        result = await self._runner.run(
            CommandRequest(
                executable=self.executable,
                arguments=self.build_arguments(request),
                cwd=request.cwd,
                timeout=request.timeout,
                max_output_bytes=request.max_output_bytes,
            ),
            on_stdout_line=handle,
        )
        return result.model_copy(update={"stdout": self.render_output(result.stdout)})

    def render_output(self, output: str) -> str:
        """Extract the final answer from provider-native JSONL output.

        The default joins OpenCode ``text`` parts, Codex ``agent_message`` items, and
        Claude Code or Cursor ``result`` events. Adapters whose CLI emits a different
        final-answer shape override this method.

        Args:
            output: Captured standard output of the CLI.

        Returns:
            Human-readable text shown to users and stored as the task result.
        """
        parts: list[str] = []
        for line in output.splitlines():
            event = parse_event(line)
            if event is None:
                continue
            if event.type == "text" and event.part is not None:
                parts.append(event.part.text)
            elif event.type == "item.completed" and event.item is not None:
                if event.item.type == "agent_message":
                    parts.append(event.item.text)
            elif event.type == "result" and event.result is not None:
                parts.append(event.result)
        return "\n".join(parts)


CliAdapterFactory = Callable[[str], CodingAgentCliAdapter]
