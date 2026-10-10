"""Native Kilo CLI argument translation."""

from collections.abc import Sequence
from typing import Literal

from pydantic import model_validator

from curupira.agents.base import CodingAgentCliAdapter
from curupira.hooks import hookimpl
from curupira.models import CodingTaskRequest
from curupira.models.base import NonEmptyString
from curupira.models.profiles import CliProfileBase


class KiloCliProfile(CliProfileBase):
    """Kilo options, including native custom-agent and reasoning-variant selection.

    Attributes:
        provider: Discriminator identifying the Kilo CLI.
        agent: Optional configured Kilo agent name.
        effort: Optional provider-specific reasoning variant.
        auto_approve: Whether Kilo auto-approves permissions not explicitly denied.
    """

    provider: Literal["kilo"] = "kilo"
    agent: NonEmptyString | None = None
    effort: NonEmptyString | None = None
    auto_approve: bool = False

    @model_validator(mode="after")
    def validate_model_format(self) -> "KiloCliProfile":
        """Require the provider/model format when a model is configured."""
        if self.model is not None and "/" not in self.model:
            raise ValueError("Kilo model must use the provider/model format")
        return self


class KiloCliAdapter(CodingAgentCliAdapter):
    """Invoke Kilo's OpenCode-compatible JSONL run interface."""

    executable = "kilo"
    provider = "kilo"
    profile_model = KiloCliProfile
    display_name = "Kilo CLI"
    install_url = "https://kilo.ai/docs/code-with-ai/platforms/cli"

    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        """Build a noninteractive Kilo invocation with optional overrides."""
        profile = request.profile
        if not isinstance(profile, KiloCliProfile):
            raise ValueError("Kilo CLI requires a Kilo profile")
        arguments = ["run", "--format", "json"]
        if request.session_id is not None:
            arguments.extend(("--session", request.session_id))
        for flag, value in (
            ("--model", profile.model),
            ("--agent", profile.agent),
            ("--variant", profile.effort),
        ):
            if value is not None:
                arguments.extend((flag, value))
        if profile.auto_approve:
            arguments.append("--auto")
        return (*arguments, "--", request.message)


@hookimpl
def curupira_coding_agent_adapters() -> Sequence[type[CodingAgentCliAdapter]]:
    """Contribute the Kilo CLI adapter."""
    return (KiloCliAdapter,)
