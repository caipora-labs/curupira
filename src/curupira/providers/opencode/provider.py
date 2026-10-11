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
        (https://opencode.ai/docs/cli/). Omits the ``run`` subcommand, ``--format
        json``, and ``--variant`` (``--variant`` is documented only under ``run``).
        Profile ``effort`` is therefore not applied interactively. Prompts use
        ``--prompt=<text>`` so a leading ``-`` is not parsed as a flag.
        """
        self.ensure_interactive_model_resolved(model)
        if not isinstance(profile, OpenCodeCliProfile):
            raise ValueError("OpenCode requires an OpenCode profile")
        arguments: list[str] = [self.executable]
        notes: list[str] = []
        if model is not None:
            arguments.extend(("--model", model))
        if profile.agent is not None:
            arguments.extend(("--agent", profile.agent))
        if profile.effort is not None:
            notes.append(
                "profile effort is not applied interactively; --variant is "
                "documented only for opencode run"
            )
        if prompt is not None:
            arguments.append(f"--prompt={prompt}")
        if profile.auto_approve:
            arguments.append("--auto")
        return InteractiveLaunchSpec(argv=tuple(arguments), cwd=cwd, notes=tuple(notes))


@hookimpl
def curupira_coding_agent_adapters() -> Sequence[type[CodingAgentCliAdapter]]:
    """Contribute the OpenCode adapter."""
    return (OpenCodeCliAdapter,)
