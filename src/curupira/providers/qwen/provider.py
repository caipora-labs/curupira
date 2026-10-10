"""Native Qwen Code CLI argument translation."""

from collections.abc import Sequence
from typing import Annotated, Literal

from pydantic import Field
from typing_extensions import override

from curupira.agents.base import CodingAgentCliAdapter
from curupira.hooks import hookimpl
from curupira.models import CliProfileBase, CodingTaskRequest


class QwenCodeCliProfile(CliProfileBase):
    """Options supported by the Qwen Code CLI.

    Attributes:
        provider: Discriminator identifying the Qwen Code CLI.
        model: Optional Qwen Code model identifier.
        approval_mode: Optional native approval policy.
        max_session_turns: Optional maximum number of turns for one session.
    """

    provider: Literal["qwen"] = "qwen"
    approval_mode: Literal["plan", "default", "auto-edit", "auto", "yolo"] | None = None
    max_session_turns: Annotated[int, Field(strict=True, ge=1)] | None = None


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


@hookimpl
def curupira_coding_agent_adapters() -> Sequence[type[CodingAgentCliAdapter]]:
    """Contribute the Qwen Code adapter."""
    return (QwenCodeCliAdapter,)
