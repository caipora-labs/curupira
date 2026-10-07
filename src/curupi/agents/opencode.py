"""Native OpenCode CLI argument translation."""

from curupi.agents.base import CodingAgentCliAdapter
from curupi.models import CodingTaskRequest, OpenCodeCliProfile


class OpenCodeCliAdapter(CodingAgentCliAdapter):
    """Select existing OpenCode agents by their native names."""

    executable = "opencode"
    provider = "opencode"

    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        """Build a noninteractive OpenCode invocation with optional overrides."""
        profile = request.profile
        if not isinstance(profile, OpenCodeCliProfile):
            raise ValueError("OpenCode requires an OpenCode profile")
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
