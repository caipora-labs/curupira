"""Native GitHub Copilot CLI argument translation."""

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from typing_extensions import override

from curupira.agents.base import CodingAgentCliAdapter
from curupira.agents.interactive import InteractiveLaunchSpec
from curupira.hooks import hookimpl
from curupira.models import CliProfileBase, CodingTaskRequest
from curupira.models.base import NonEmptyString


class CopilotCliProfile(CliProfileBase):
    """GitHub Copilot CLI profile. Set ``provider`` to ``\"copilot\"`` in TOML."""

    provider: Literal["copilot"] = Field(
        default="copilot",
        description='Discriminator identifying the GitHub Copilot CLI. Must be "copilot".',
    )
    agent: NonEmptyString | None = Field(
        default=None,
        description=(
            "Optional configured Copilot custom-agent name. When set, the adapter passes "
            "``--agent=<name>``; when unset, that flag is omitted."
        ),
    )
    effort: Literal["low", "medium", "high", "xhigh", "max"] | None = Field(
        default=None,
        description=(
            "Optional Copilot reasoning effort. Allowed values: low, medium, high, "
            "xhigh, max. When set, the adapter passes ``--reasoning-effort=<value>``; "
            "when unset, that flag is omitted."
        ),
    )
    allow_all_tools: bool = Field(
        default=False,
        description=(
            "When true, the adapter adds ``--allow-all-tools``. When false (the "
            "default), that flag is omitted."
        ),
    )
    allow_tools: tuple[NonEmptyString, ...] = Field(
        default=(),
        description=(
            "Explicit native tool permission patterns to allow. When non-empty, the "
            "adapter passes ``--allow-tool=<patterns>`` as a comma-separated list. "
            "Entries must not contain commas. When empty (the default), that flag is "
            "omitted."
        ),
    )
    deny_tools: tuple[NonEmptyString, ...] = Field(
        default=(),
        description=(
            "Explicit native tool permission patterns to deny. When non-empty, the "
            "adapter passes ``--deny-tool=<patterns>`` as a comma-separated list. "
            "Entries must not contain commas. When empty (the default), that flag is "
            "omitted."
        ),
    )

    @field_validator("allow_tools", "deny_tools")
    @classmethod
    def validate_tool_patterns(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Reject commas that would change the CLI's comma-separated tool list."""
        if any("," in tool for tool in value):
            raise ValueError("Copilot tool entries must not contain commas")
        return value


class CopilotCliAdapter(CodingAgentCliAdapter):
    """Run Copilot programmatically with a Curupira-owned session identifier."""

    executable = "copilot"
    provider = "copilot"
    profile_model = CopilotCliProfile
    display_name = "GitHub Copilot CLI"
    install_url = (
        "https://docs.github.com/en/copilot/how-tos/copilot-cli/"
        "set-up-copilot-cli/install-copilot-cli"
    )
    assigns_session_id = True
    # Copilot documents ``--model=auto`` for automatic model selection
    # (https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference).
    auto_model = "auto"

    @override
    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        """Build an autonomous prompt invocation with optional profile settings."""
        profile = request.profile
        if not isinstance(profile, CopilotCliProfile):
            raise ValueError("GitHub Copilot CLI requires a Copilot profile")

        session_id = request.new_session_id or request.session_id
        if session_id is None:
            raise ValueError("GitHub Copilot CLI requires a session identifier")

        arguments = [
            "--output-format=json",
            "--no-ask-user",
            f"--session-id={session_id}",
        ]
        for flag, value in (
            ("--model", profile.model),
            ("--agent", profile.agent),
            ("--reasoning-effort", profile.effort),
        ):
            if value is not None:
                arguments.append(f"{flag}={value}")
        if profile.allow_all_tools:
            arguments.append("--allow-all-tools")
        if profile.allow_tools:
            arguments.append(f"--allow-tool={','.join(profile.allow_tools)}")
        if profile.deny_tools:
            arguments.append(f"--deny-tool={','.join(profile.deny_tools)}")
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
        """Build an interactive ``copilot`` TUI launch.

        Official docs: ``copilot`` launches the interactive UI; ``--interactive=PROMPT``
        seeds the first turn, and ``--model``, ``--agent``, and tool-permission flags
        apply (https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference).
        Omits ``--output-format=json``, ``--no-ask-user``, ``--session-id``, and
        ``--prompt`` (programmatic / exit-after-completion).
        """
        self.ensure_interactive_model_resolved(model)
        if not isinstance(profile, CopilotCliProfile):
            raise ValueError("GitHub Copilot CLI requires a Copilot profile")
        arguments: list[str] = [self.executable]
        for flag, value in (
            ("--model", model),
            ("--agent", profile.agent),
            ("--reasoning-effort", profile.effort),
        ):
            if value is not None:
                arguments.append(f"{flag}={value}")
        if profile.allow_all_tools:
            arguments.append("--allow-all-tools")
        if profile.allow_tools:
            arguments.append(f"--allow-tool={','.join(profile.allow_tools)}")
        if profile.deny_tools:
            arguments.append(f"--deny-tool={','.join(profile.deny_tools)}")
        if prompt is not None:
            # Equals form keeps leading-dash prompts from being parsed as flags.
            arguments.append(f"--interactive={prompt}")
        return InteractiveLaunchSpec(argv=tuple(arguments), cwd=cwd)

    @override
    def render_output(self, output: str) -> str:
        """Return Copilot's JSONL unchanged until its prompt event schema is verified."""
        return output


@hookimpl
def curupira_coding_agent_adapters() -> Sequence[type[CodingAgentCliAdapter]]:
    """Contribute the GitHub Copilot CLI adapter."""
    return (CopilotCliAdapter,)
