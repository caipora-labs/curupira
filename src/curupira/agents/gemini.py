"""Gemini CLI profile and native argument translation."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError
from typing_extensions import override

from curupira.agents.base import CodingAgentCliAdapter
from curupira.agents.registry import register
from curupira.models import CliProfileBase, CodingTaskRequest


class GeminiCliProfile(CliProfileBase):
    """Gemini CLI options that Curupira maps to native command-line flags.

    Attributes:
        provider: Discriminator identifying the Gemini CLI.
        model: Optional Gemini model identifier, inherited from the base profile.
        approval_mode: Optional native Gemini approval policy.
        skip_trust: Whether to trust the current workspace for this session.
    """

    provider: Literal["gemini"] = "gemini"
    approval_mode: Literal["default", "auto_edit", "yolo", "plan"] | None = None
    skip_trust: bool = False


class _GeminiStreamEvent(BaseModel):
    """Relevant fields from a Gemini stream-json event."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    type: str = ""
    role: str | None = None
    content: str = ""
    delta: bool = False


class GeminiCliAdapter(CodingAgentCliAdapter):
    """Run Gemini CLI in headless JSONL mode and render assistant message events."""

    executable = "gemini"
    provider = "gemini"
    profile_model = GeminiCliProfile
    display_name = "Gemini CLI"
    install_url = "https://github.com/google-gemini/gemini-cli"

    @override
    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        """Build a headless invocation using Gemini's native profile options."""
        profile = request.profile
        if not isinstance(profile, GeminiCliProfile):
            raise ValueError("Gemini CLI requires a Gemini profile")

        arguments = ["--output-format", "stream-json"]
        if request.session_id is not None:
            arguments.extend(("--resume", request.session_id))
        if profile.model is not None:
            arguments.extend(("--model", profile.model))
        if profile.approval_mode is not None:
            arguments.extend(("--approval-mode", profile.approval_mode))
        if profile.skip_trust:
            arguments.append("--skip-trust")
        arguments.append(f"--prompt={request.message}")
        return tuple(arguments)

    @override
    def render_output(self, output: str) -> str:
        """Join assistant message content while preserving message boundaries.

        Consecutive assistant delta events form one message. Other event types are
        ignored and end any pending delta message.

        Args:
            output: Captured Gemini stream-json output, one JSON event per line.

        Returns:
            Assistant text from the stream, with separate messages newline-delimited.
        """
        messages: list[str] = []
        delta_chunks: list[str] = []

        for line in output.splitlines():
            try:
                event = _GeminiStreamEvent.model_validate_json(line)
            except ValidationError:
                event = None

            if event is not None and event.type == "message" and event.role == "assistant":
                if event.delta:
                    delta_chunks.append(event.content)
                    continue
                if delta_chunks:
                    messages.append("".join(delta_chunks))
                    delta_chunks.clear()
                messages.append(event.content)
                continue

            if delta_chunks:
                messages.append("".join(delta_chunks))
                delta_chunks.clear()

        if delta_chunks:
            messages.append("".join(delta_chunks))
        return "\n".join(messages)


register(GeminiCliAdapter)
