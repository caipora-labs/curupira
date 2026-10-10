"""Native pi coding-agent CLI argument translation."""

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator
from typing_extensions import override

from curupira.agents.base import CodingAgentCliAdapter
from curupira.hooks import hookimpl
from curupira.models import CliProfileBase, CodingTaskRequest
from curupira.models.base import NonEmptyString


class PiCliProfile(CliProfileBase):
    """Options supported by the pi coding-agent CLI.

    Attributes:
        provider: Discriminator identifying the pi CLI.
        model_provider: Optional provider constraint for the selected model.
        effort: Optional pi thinking level.
        tools: Tool allowlist passed to pi.
        exclude_tools: Tools excluded from pi's available tools.
        approve: Explicit project-trust decision for this process.
    """

    provider: Literal["pi"] = "pi"
    model_provider: NonEmptyString | None = None
    effort: Literal["off", "minimal", "low", "medium", "high", "xhigh", "max"] | None = None
    tools: tuple[NonEmptyString, ...] = ()
    exclude_tools: tuple[NonEmptyString, ...] = ()
    approve: bool | None = None

    @model_validator(mode="after")
    def validate_model_provider(self) -> "PiCliProfile":
        """Require a model whenever a provider is explicitly selected."""
        if self.model_provider is not None and self.model is None:
            raise ValueError("model_provider requires model")
        return self


class PiContentBlock(BaseModel):
    """Content block in a pi message event."""

    model_config = ConfigDict(extra="ignore")

    type: str = ""
    text: str | None = None


class PiMessage(BaseModel):
    """Message payload in a pi JSON event."""

    model_config = ConfigDict(extra="ignore")

    role: str = ""
    content: tuple[PiContentBlock, ...] = ()


class PiEvent(BaseModel):
    """Relevant fields in a pi JSON-mode event."""

    model_config = ConfigDict(extra="ignore")

    type: str = ""
    id: str | None = None
    message: PiMessage | None = None


def parse_pi_event(line: str) -> PiEvent | None:
    """Parse one pi JSONL record, ignoring non-event output."""
    try:
        return PiEvent.model_validate_json(line)
    except ValidationError:
        return None


class PiCliAdapter(CodingAgentCliAdapter):
    """Run pi in JSON mode, optionally resuming a known project session."""

    executable = "pi"
    provider = "pi"
    profile_model = PiCliProfile
    display_name = "pi"
    install_url = "https://pi.dev/docs/latest"

    @override
    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        """Build a JSON-mode pi invocation with the configured native options."""
        profile = request.profile
        if not isinstance(profile, PiCliProfile):
            raise ValueError("pi requires a pi profile")

        arguments = ["--mode", "json"]
        if request.session_id is not None:
            arguments.extend(("--session", request.session_id))
        if profile.model_provider is not None:
            arguments.extend(("--provider", profile.model_provider))
        if profile.model is not None:
            arguments.extend(("--model", profile.model))
        if profile.effort is not None:
            arguments.extend(("--thinking", profile.effort))
        if profile.tools:
            arguments.extend(("--tools", ",".join(profile.tools)))
        if profile.exclude_tools:
            arguments.extend(("--exclude-tools", ",".join(profile.exclude_tools)))
        if profile.approve is True:
            arguments.append("--approve")
        elif profile.approve is False:
            arguments.append("--no-approve")
        return (*arguments, "--", request.message)

    @override
    def session_id_from_line(self, line: str) -> str | None:
        """Read pi's native session identifier from its session header."""
        event = parse_pi_event(line)
        return event.id if event is not None and event.type == "session" else None

    @override
    def render_output(self, output: str) -> str:
        """Join assistant text blocks from pi's authoritative message-end events."""
        parts: list[str] = []
        for line in output.splitlines():
            event = parse_pi_event(line)
            if (
                event is None
                or event.type != "message_end"
                or event.message is None
                or event.message.role != "assistant"
            ):
                continue
            parts.extend(
                block.text
                for block in event.message.content
                if block.type == "text" and block.text is not None
            )
        return "\n".join(parts)


@hookimpl
def curupira_coding_agent_adapters() -> Sequence[type[CodingAgentCliAdapter]]:
    """Contribute the pi adapter."""
    return (PiCliAdapter,)
