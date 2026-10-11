"""Native Kilo CLI argument translation."""

from collections.abc import Sequence
from typing import Literal

from pydantic import Field, model_validator

from curupira.agents.base import CodingAgentCliAdapter
from curupira.hooks import hookimpl
from curupira.models import CodingTaskRequest
from curupira.models.base import NonEmptyString
from curupira.models.profiles import CliProfileBase


class KiloCliProfile(CliProfileBase):
    """Kilo CLI profile. Set ``provider`` to ``\"kilo\"`` in TOML.

    When ``model`` is set it must use the ``provider/model`` format.
    """

    provider: Literal["kilo"] = Field(
        default="kilo",
        description='Discriminator identifying the Kilo CLI. Must be "kilo".',
    )
    agent: NonEmptyString | None = Field(
        default=None,
        description=(
            "Optional configured Kilo agent name. When set, the adapter passes "
            "``--agent``; when unset, that flag is omitted."
        ),
    )
    effort: NonEmptyString | None = Field(
        default=None,
        description=(
            "Optional Kilo reasoning variant. When set, the adapter passes "
            "``--variant``; when unset, that flag is omitted."
        ),
    )
    auto_approve: bool = Field(
        default=False,
        description=(
            "When true, the adapter adds ``--auto``. When false (the default), that "
            "flag is omitted."
        ),
    )

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
