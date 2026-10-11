"""Native pi coding-agent CLI argument translation."""

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from typing_extensions import override

from curupira.agents.base import CodingAgentCliAdapter
from curupira.agents.interactive import InteractiveLaunchSpec
from curupira.hooks import hookimpl
from curupira.models import CliProfileBase, CodingTaskRequest
from curupira.models.base import NonEmptyString


class PiCliProfile(CliProfileBase):
    """pi coding-agent CLI profile. Set ``provider`` to ``\"pi\"`` in TOML."""

    provider: Literal["pi"] = Field(
        default="pi",
        description='Discriminator identifying the pi CLI. Must be "pi".',
    )
    model_provider: NonEmptyString | None = Field(
        default=None,
        description=(
            "Optional provider constraint for the selected model. Requires ``model`` "
            "when set. When set, the adapter passes ``--provider``; when unset, that "
            "flag is omitted."
        ),
    )
    effort: Literal["off", "minimal", "low", "medium", "high", "xhigh", "max"] | None = Field(
        default=None,
        description=(
            "Optional pi thinking level. Allowed values: off, minimal, low, medium, "
            "high, xhigh, max. When set, the adapter passes ``--thinking``; when unset, "
            "that flag is omitted."
        ),
    )
    tools: tuple[NonEmptyString, ...] = Field(
        default=(),
        description=(
            "Tool allowlist passed to pi. When non-empty, the adapter passes "
            "``--tools`` as a comma-separated list. When empty (the default), that "
            "flag is omitted."
        ),
    )
    exclude_tools: tuple[NonEmptyString, ...] = Field(
        default=(),
        description=(
            "Tools excluded from pi's available tools. When non-empty, the adapter "
            "passes ``--exclude-tools`` as a comma-separated list. When empty (the "
            "default), that flag is omitted."
        ),
    )
    approve: bool | None = Field(
        default=None,
        description=(
            "Optional explicit project-trust decision. When true, the adapter adds "
            "``--approve``; when false, ``--no-approve``; when unset, neither flag is "
            "passed."
        ),
    )

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
    def interactive_launch(
        self,
        profile: CliProfileBase,
        *,
        model: str | None,
        prompt: str | None,
        cwd: Path,
    ) -> InteractiveLaunchSpec:
        """Build an interactive ``pi`` TUI launch.

        Official docs: ``pi`` opens the terminal UI when stdin/stdout are TTYs;
        positional messages seed the first prompt, and ``--model``, ``--provider``,
        ``--thinking``, tool, and approve flags apply (https://pi.dev/docs/latest/cli).
        ``--provider`` requires ``--model``; it is emitted only when ``model`` is set
        and equals the profile's own ``model`` so the provider is never paired with a
        different assistant model. Omits ``--mode json``. Prompts follow ``--``.
        """
        self.ensure_interactive_model_resolved(model)
        if not isinstance(profile, PiCliProfile):
            raise ValueError("pi requires a pi profile")
        arguments: list[str] = [self.executable]
        if model is not None:
            if profile.model_provider is not None and model == profile.model:
                arguments.extend(("--provider", profile.model_provider))
            arguments.extend(("--model", model))
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
        if prompt is not None:
            arguments.extend(("--", prompt))
        return InteractiveLaunchSpec(argv=tuple(arguments), cwd=cwd)

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
