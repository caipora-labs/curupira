"""Native Claude Code CLI argument translation."""

from collections.abc import Sequence
from pathlib import Path

from typing_extensions import override

from curupira.agents.base import CodingAgentCliAdapter
from curupira.agents.interactive import InteractiveLaunchSpec
from curupira.hooks import hookimpl
from curupira.models import ClaudeCodeCliProfile, CliProfileBase, CodingTaskRequest


class ClaudeCodeCliAdapter(CodingAgentCliAdapter):
    """Invoke an existing Claude Code custom agent without defining a new one."""

    executable = "claude"
    provider = "claude"
    profile_model = ClaudeCodeCliProfile
    display_name = "Claude Code"
    install_url = "https://code.claude.com/docs/en/cli-reference"

    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        """Build a print-mode invocation preserving native policies by default."""
        profile = request.profile
        if not isinstance(profile, ClaudeCodeCliProfile):
            raise ValueError("Claude Code requires a Claude profile")
        arguments = ["-p", "--output-format", "stream-json", "--verbose"]
        if request.session_id is not None:
            arguments.extend(("--resume", request.session_id))
        for flag, value in (
            ("--model", profile.model),
            ("--agent", profile.agent),
            ("--effort", profile.effort),
            ("--permission-mode", profile.permission_mode),
            ("--permission-prompts", profile.permission_prompts),
        ):
            if value is not None:
                arguments.extend((flag, value))
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
        """Build an interactive ``claude`` TUI launch.

        Official docs: interactive ``claude`` / ``claude "query"``, plus ``--model``,
        ``--agent``, ``--effort``, and ``--permission-mode``
        (https://code.claude.com/docs/en/cli-reference). Omits print-mode flags
        (``-p``, ``--output-format``, ``--verbose``) and ``--permission-prompts``
        (documented for print mode only). Initial prompts are passed after ``--`` so a
        leading ``-`` (for example skill front matter ``---``) is not parsed as a flag.
        """
        self.ensure_interactive_model_resolved(model)
        if not isinstance(profile, ClaudeCodeCliProfile):
            raise ValueError("Claude Code requires a Claude profile")
        arguments: list[str] = [self.executable]
        for flag, value in (
            ("--model", model),
            ("--agent", profile.agent),
            ("--effort", profile.effort),
            ("--permission-mode", profile.permission_mode),
        ):
            if value is not None:
                arguments.extend((flag, value))
        if prompt is not None:
            arguments.extend(("--", prompt))
        return InteractiveLaunchSpec(argv=tuple(arguments), cwd=cwd)


@hookimpl
def curupira_coding_agent_adapters() -> Sequence[type[CodingAgentCliAdapter]]:
    """Contribute the Claude Code adapter."""
    return (ClaudeCodeCliAdapter,)
