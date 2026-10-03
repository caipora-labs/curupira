"""Native Cursor CLI argument translation."""

from gh_dispatch.coding_agents import CodingAgentCliAdapter
from gh_dispatch.models import CodingTaskRequest, CursorCliProfile


class CursorCliAdapter(CodingAgentCliAdapter):
    """Run the Cursor CLI without treating execution modes as custom agents."""

    executable = "agent"
    provider = "cursor"

    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        """Build a headless invocation with explicit trust/force overrides only."""
        profile = request.profile
        if not isinstance(profile, CursorCliProfile):
            raise ValueError("Cursor requires a Cursor profile")
        arguments = ["--print", "--output-format", "stream-json"]
        if request.session_id is not None:
            arguments.extend(("--resume", request.session_id))
        if profile.model is not None:
            arguments.extend(("--model", profile.model))
        if profile.force:
            arguments.append("--force")
        if profile.trust:
            arguments.append("--trust")
        return (*arguments, "--", request.message)
