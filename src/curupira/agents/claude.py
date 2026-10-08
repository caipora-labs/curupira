"""Native Claude Code CLI argument translation."""

from curupira.agents.base import CodingAgentCliAdapter
from curupira.agents.registry import register
from curupira.models import ClaudeCodeCliProfile, CodingTaskRequest


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


register(ClaudeCodeCliAdapter)
