"""Native Cursor CLI argument translation."""

from collections.abc import Sequence

from curupira.agents.base import CodingAgentCliAdapter
from curupira.hooks import hookimpl
from curupira.models import CodingTaskRequest, CursorCliProfile


class CursorCliAdapter(CodingAgentCliAdapter):
    """Map the profile's agent selection to Cursor's native execution mode."""

    executable = "agent"
    provider = "cursor"
    profile_model = CursorCliProfile
    display_name = "Cursor"
    install_url = "https://docs.cursor.com/en/cli/overview"
    # Cursor changelog: new installs default to Auto; switch anytime with ``/model`` or
    # ``--model`` (https://cursor.com/docs/cli/changelog). The adapter passes the model
    # via ``--model`` below; confirm the literal id ``auto`` with ``agent models`` on a
    # real install.
    auto_model = "auto"

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


@hookimpl
def curupira_coding_agent_adapters() -> Sequence[type[CodingAgentCliAdapter]]:
    """Contribute the Cursor adapter."""
    return (CursorCliAdapter,)
