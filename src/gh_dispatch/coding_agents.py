"""Behavioral interface and factory for external coding-agent CLI adapters."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import ClassVar

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, ValidationError

from gh_dispatch.clients.process import AsyncProcessRunner
from gh_dispatch.errors import UnsupportedCodingAgentError
from gh_dispatch.models import CodingTaskRequest, CommandRequest, ProcessResult

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
    """Invoke a native CLI; agent definitions are owned by that external tool."""

    executable: ClassVar[str]
    provider: ClassVar[str]

    def __init__(self, runner: AsyncProcessRunner | None = None) -> None:
        self._runner = runner or AsyncProcessRunner()

    @abstractmethod
    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        """Translate a validated profile into native CLI arguments."""

    async def run_task(
        self,
        request: CodingTaskRequest,
        *,
        on_session_started: SessionStartedCallback | None = None,
    ) -> ProcessResult:
        """Run headlessly and report native session identifiers while streaming."""
        if request.profile.provider != self.provider:
            raise UnsupportedCodingAgentError(
                f"{self.provider} adapter cannot use {request.profile.provider} profile"
            )
        reported: str | None = None

        async def handle(line: str) -> None:
            nonlocal reported
            event = parse_event(line)
            if event is not None and event.session_id and event.session_id != reported:
                reported = event.session_id
                if on_session_started is not None:
                    await on_session_started(reported)

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
        """Extract human-readable text from provider-native JSONL output."""
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


def create_cli_adapter(
    provider: str, runner: AsyncProcessRunner | None = None
) -> CodingAgentCliAdapter:
    """Construct the native adapter for a supported provider."""
    from gh_dispatch.clients.claude import ClaudeCodeCliAdapter
    from gh_dispatch.clients.codex import CodexCliAdapter
    from gh_dispatch.clients.cursor import CursorCliAdapter
    from gh_dispatch.clients.opencode import OpenCodeCliAdapter

    adapters: dict[str, type[CodingAgentCliAdapter]] = {
        "opencode": OpenCodeCliAdapter,
        "codex": CodexCliAdapter,
        "claude": ClaudeCodeCliAdapter,
        "cursor": CursorCliAdapter,
    }
    try:
        adapter = adapters[provider]
    except KeyError as error:
        raise UnsupportedCodingAgentError(
            f"unsupported coding agent provider: {provider}"
        ) from error
    return adapter(runner)
