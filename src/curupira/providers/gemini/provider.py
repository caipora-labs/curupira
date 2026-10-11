"""Gemini CLI profile and native argument translation."""

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing_extensions import override

from curupira.agents.base import CodingAgentCliAdapter
from curupira.agents.interactive import InteractiveLaunchSpec
from curupira.hooks import hookimpl
from curupira.models import CliProfileBase, CodingTaskRequest


class GeminiCliProfile(CliProfileBase):
    """Gemini CLI profile. Set ``provider`` to ``\"gemini\"`` in TOML."""

    provider: Literal["gemini"] = Field(
        default="gemini",
        description='Discriminator identifying the Gemini CLI. Must be "gemini".',
    )
    approval_mode: Literal["default", "auto_edit", "yolo", "plan"] | None = Field(
        default=None,
        description=(
            "Optional Gemini approval policy. Allowed values: default, auto_edit, yolo, "
            "plan. When set, the adapter passes ``--approval-mode``; when unset, that "
            "flag is omitted."
        ),
    )
    skip_trust: bool = Field(
        default=False,
        description=(
            "When true, the adapter adds ``--skip-trust``. When false (the default), "
            "that flag is omitted."
        ),
    )


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
    # Gemini CLI documents ``--model`` default ``auto``
    # (https://geminicli.com/docs/cli/cli-reference/).
    auto_model = "auto"

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
    def interactive_launch(
        self,
        profile: CliProfileBase,
        *,
        model: str | None,
        prompt: str | None,
        cwd: Path,
    ) -> InteractiveLaunchSpec:
        """Build an interactive ``gemini`` REPL launch.

        Official docs: ``gemini`` starts interactive mode; ``--model``,
        ``--approval-mode``, and ``--skip-trust`` apply, and
        ``--prompt-interactive`` / ``-i`` seeds a prompt then continues
        (https://geminicli.com/docs/cli/cli-reference/). Omits ``--output-format`` and
        ``--prompt`` (``--prompt`` forces non-interactive mode). Prompts use
        ``--prompt-interactive=<text>`` so a leading ``-`` is not parsed as a flag.
        """
        self.ensure_interactive_model_resolved(model)
        if not isinstance(profile, GeminiCliProfile):
            raise ValueError("Gemini CLI requires a Gemini profile")
        arguments: list[str] = [self.executable]
        if model is not None:
            arguments.extend(("--model", model))
        if profile.approval_mode is not None:
            arguments.extend(("--approval-mode", profile.approval_mode))
        if profile.skip_trust:
            arguments.append("--skip-trust")
        if prompt is not None:
            arguments.append(f"--prompt-interactive={prompt}")
        return InteractiveLaunchSpec(argv=tuple(arguments), cwd=cwd)

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


@hookimpl
def curupira_coding_agent_adapters() -> Sequence[type[CodingAgentCliAdapter]]:
    """Contribute the Gemini CLI adapter."""
    return (GeminiCliAdapter,)
