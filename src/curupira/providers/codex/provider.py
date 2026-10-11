"""Native Codex CLI argument translation."""

import json
from collections.abc import Sequence
from pathlib import Path

from typing_extensions import override

from curupira.agents.base import CodingAgentCliAdapter
from curupira.agents.interactive import InteractiveLaunchSpec
from curupira.hooks import hookimpl
from curupira.models import CliProfileBase, CodexCliProfile, CodingTaskRequest


class CodexCliAdapter(CodingAgentCliAdapter):
    """Invoke Codex exec with an existing configuration profile and native effort setting."""

    executable = "codex"
    provider = "codex"
    profile_model = CodexCliProfile
    display_name = "Codex"
    install_url = "https://developers.openai.com/codex/cli/"

    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        """Build the native initial or resumed exec command with optional profile options."""
        profile = request.profile
        if not isinstance(profile, CodexCliProfile):
            raise ValueError("Codex requires a Codex profile")
        arguments = ["exec"]
        if request.session_id is not None:
            arguments.extend(("resume", request.session_id))
        if profile.model is not None:
            arguments.extend(("--model", profile.model))
        if profile.agent is not None:
            arguments.extend(("--profile", profile.agent))
        if profile.effort is not None:
            arguments.extend(("--config", f"model_reasoning_effort={json.dumps(profile.effort)}"))
        if profile.sandbox is not None:
            arguments.extend(("--sandbox", profile.sandbox))
        if profile.auto_review:
            arguments.extend(
                (
                    "--config",
                    'approval_policy="on-request"',
                    "--config",
                    'approvals_reviewer="auto_review"',
                )
            )
        return (*arguments, "--json", "--", request.message)

    @override
    def interactive_launch(
        self,
        profile: CliProfileBase,
        *,
        model: str | None,
        prompt: str | None,
        cwd: Path,
    ) -> InteractiveLaunchSpec:
        """Build an interactive ``codex`` TUI launch.

        Official docs: ``codex`` launches the TUI with global flags and an optional
        prompt (https://developers.openai.com/codex/cli/reference/). Omits the
        ``exec`` subcommand and ``--json`` headless flags while reusing ``--model``,
        ``--profile``, ``--sandbox``, and ``--config``. Effort/approval ``--config``
        keys are copied from the headless mapping; the reference documents
        ``--config key=value`` but not those key names specifically. Prompts follow
        ``--`` so a leading ``-`` is not parsed as a flag.
        """
        self.ensure_interactive_model_resolved(model)
        if not isinstance(profile, CodexCliProfile):
            raise ValueError("Codex requires a Codex profile")
        arguments: list[str] = [self.executable]
        notes: list[str] = []
        if model is not None:
            arguments.extend(("--model", model))
        if profile.agent is not None:
            arguments.extend(("--profile", profile.agent))
        if profile.effort is not None:
            arguments.extend(("--config", f"model_reasoning_effort={json.dumps(profile.effort)}"))
            notes.append(
                "model_reasoning_effort is passed via --config; the Codex reference "
                "documents --config but not this key name"
            )
        if profile.sandbox is not None:
            arguments.extend(("--sandbox", profile.sandbox))
        if profile.auto_review:
            arguments.extend(
                (
                    "--config",
                    'approval_policy="on-request"',
                    "--config",
                    'approvals_reviewer="auto_review"',
                )
            )
            notes.append(
                "auto_review approval_policy/approvals_reviewer --config keys are "
                "copied from the headless mapping and are not named in the Codex "
                "interactive reference"
            )
        if prompt is not None:
            arguments.extend(("--", prompt))
        return InteractiveLaunchSpec(argv=tuple(arguments), cwd=cwd, notes=tuple(notes))


@hookimpl
def curupira_coding_agent_adapters() -> Sequence[type[CodingAgentCliAdapter]]:
    """Contribute the Codex adapter."""
    return (CodexCliAdapter,)
