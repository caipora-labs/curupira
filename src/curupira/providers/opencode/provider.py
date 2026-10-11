"""Native OpenCode CLI argument translation."""

from collections.abc import Sequence
from pathlib import Path

from typing_extensions import override

from curupira.agents.base import CodingAgentCliAdapter
from curupira.agents.interactive import InteractiveLaunchSpec
from curupira.hooks import hookimpl
from curupira.models import CliProfileBase, CodingTaskRequest, OpenCodeCliProfile


class OpenCodeCliAdapter(CodingAgentCliAdapter):
    """Select existing OpenCode agents by their native names."""

    executable = "opencode"
    provider = "opencode"
    profile_model = OpenCodeCliProfile
    display_name = "OpenCode"
    install_url = "https://opencode.ai/"

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

    @override
    def interactive_launch(
        self,
        profile: CliProfileBase,
        *,
        model: str | None,
        prompt: str | None,
        cwd: Path,
    ) -> InteractiveLaunchSpec:
        """Build an interactive ``opencode`` TUI launch.

        Official docs: ``opencode`` starts the TUI; ``--model``, ``--agent``,
        ``--prompt``, and ``--auto`` apply to that entry point
        (https://opencode.ai/docs/cli/). Omits the ``run`` subcommand and
        ``--format json`` headless flags; maps profile ``effort`` to ``--variant``.
        """
        if not isinstance(profile, OpenCodeCliProfile):
            raise ValueError("OpenCode requires an OpenCode profile")
        arguments: list[str] = [self.executable]
        for flag, value in (
            ("--model", model),
            ("--agent", profile.agent),
            ("--variant", profile.effort),
            ("--prompt", prompt),
        ):
            if value is not None:
                arguments.extend((flag, value))
        if profile.auto_approve:
            arguments.append("--auto")
        return InteractiveLaunchSpec(argv=tuple(arguments), cwd=cwd)


@hookimpl
def curupira_coding_agent_adapters() -> Sequence[type[CodingAgentCliAdapter]]:
    """Contribute the OpenCode adapter."""
    return (OpenCodeCliAdapter,)
