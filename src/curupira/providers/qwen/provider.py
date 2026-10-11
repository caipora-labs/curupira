"""Native Qwen Code CLI argument translation."""

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field
from typing_extensions import override

from curupira.agents.base import CodingAgentCliAdapter
from curupira.agents.interactive import InteractiveLaunchSpec
from curupira.hooks import hookimpl
from curupira.models import CliProfileBase, CodingTaskRequest


class QwenCodeCliProfile(CliProfileBase):
    """Qwen Code CLI profile. Set ``provider`` to ``\"qwen\"`` in TOML."""

    provider: Literal["qwen"] = Field(
        default="qwen",
        description='Discriminator identifying the Qwen Code CLI. Must be "qwen".',
    )
    approval_mode: Literal["plan", "default", "auto-edit", "auto", "yolo"] | None = Field(
        default=None,
        description=(
            "Optional Qwen Code approval policy. Allowed values: plan, default, "
            "auto-edit, auto, yolo. When set, the adapter passes ``--approval-mode``; "
            "when unset, that flag is omitted."
        ),
    )
    max_session_turns: Annotated[int, Field(strict=True, ge=1)] | None = Field(
        default=None,
        description=(
            "Optional maximum number of turns for one session. Must be an integer "
            "greater than or equal to 1. When set, the adapter passes "
            "``--max-session-turns``; when unset, that flag is omitted."
        ),
    )


class QwenCodeCliAdapter(CodingAgentCliAdapter):
    """Run Qwen Code headlessly, resuming a known project-scoped session when requested."""

    executable = "qwen"
    provider = "qwen"
    profile_model = QwenCodeCliProfile
    display_name = "Qwen Code"
    install_url = "https://github.com/QwenLM/qwen-code"

    @override
    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        """Build a stream-JSON invocation using Qwen Code's native options."""
        profile = request.profile
        if not isinstance(profile, QwenCodeCliProfile):
            raise ValueError("Qwen Code requires a Qwen Code profile")

        arguments = ["--output-format", "stream-json"]
        if request.session_id is not None:
            arguments.extend(("--resume", request.session_id))
        if profile.model is not None:
            arguments.extend(("--model", profile.model))
        if profile.approval_mode is not None:
            arguments.extend(("--approval-mode", profile.approval_mode))
        if profile.max_session_turns is not None:
            arguments.extend(("--max-session-turns", str(profile.max_session_turns)))
        return (*arguments, f"--prompt={request.message}")

    @override
    def interactive_launch(
        self,
        profile: CliProfileBase,
        *,
        model: str | None,
        prompt: str | None,
        cwd: Path,
    ) -> InteractiveLaunchSpec:
        """Build an interactive ``qwen`` TUI launch.

        Official docs: ``qwen`` starts interactive mode; ``--prompt-interactive`` runs an
        initial prompt then continues interactively; ``--model``, ``--approval-mode``,
        and ``--max-session-turns`` apply
        (https://qwenlm-qwen-code.mintlify.app/cli/overview). Omits ``--output-format``
        and ``--prompt`` (headless).
        """
        if not isinstance(profile, QwenCodeCliProfile):
            raise ValueError("Qwen Code requires a Qwen Code profile")
        arguments: list[str] = [self.executable]
        if model is not None:
            arguments.extend(("--model", model))
        if profile.approval_mode is not None:
            arguments.extend(("--approval-mode", profile.approval_mode))
        if profile.max_session_turns is not None:
            arguments.extend(("--max-session-turns", str(profile.max_session_turns)))
        if prompt is not None:
            arguments.extend(("--prompt-interactive", prompt))
        return InteractiveLaunchSpec(argv=tuple(arguments), cwd=cwd)


@hookimpl
def curupira_coding_agent_adapters() -> Sequence[type[CodingAgentCliAdapter]]:
    """Contribute the Qwen Code adapter."""
    return (QwenCodeCliAdapter,)
