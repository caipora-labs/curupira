"""Native GitHub Copilot CLI argument translation."""

from typing import Literal

from pydantic import field_validator
from typing_extensions import override

from curupira.agents.base import CodingAgentCliAdapter
from curupira.agents.registry import register
from curupira.models import CliProfileBase, CodingTaskRequest
from curupira.models.base import NonEmptyString


class CopilotCliProfile(CliProfileBase):
    """GitHub Copilot CLI options for headless task execution.

    Attributes:
        provider: Discriminator identifying the GitHub Copilot CLI.
        model: Optional Copilot model identifier.
        agent: Optional configured Copilot custom-agent name.
        effort: Optional Copilot reasoning effort level.
        allow_all_tools: Whether to allow every tool supported by the CLI.
        allow_tools: Explicit native tool permission patterns to allow.
        deny_tools: Explicit native tool permission patterns to deny.
    """

    provider: Literal["copilot"] = "copilot"
    agent: NonEmptyString | None = None
    effort: Literal["low", "medium", "high", "xhigh", "max"] | None = None
    allow_all_tools: bool = False
    allow_tools: tuple[NonEmptyString, ...] = ()
    deny_tools: tuple[NonEmptyString, ...] = ()

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
    def render_output(self, output: str) -> str:
        """Return Copilot's JSONL unchanged until its prompt event schema is verified."""
        return output


register(CopilotCliAdapter)
