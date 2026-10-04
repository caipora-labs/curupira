"""Native Cursor CLI argument translation."""

from gh_dispatch.coding_agents import CodingAgentCliAdapter
from gh_dispatch.models import CodingTaskRequest, CursorCliProfile


class CursorCliAdapter(CodingAgentCliAdapter):
    """Map the profile's agent selection to Cursor's native execution mode."""

    executable = "agent"
    provider = "cursor"

    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        """Build a headless invocation with native mode and permission overrides."""
        profile = request.profile
        if not isinstance(profile, CursorCliProfile):
            raise ValueError("Cursor requires a Cursor profile")
        arguments = ["--print", "--output-format", "stream-json"]
        if request.session_id is not None:
            arguments.extend(("--resume", request.session_id))
        if profile.agent is not None:
            arguments.extend(("--mode", profile.agent))
        if profile.model is not None:
            arguments.extend(("--model", profile.model))
        if profile.force:
            arguments.append("--force")
        if profile.trust:
            arguments.append("--trust")
        return (*arguments, "--", request.message)
