"""Native Codex CLI argument translation."""

import json

from curupira.agents.base import CodingAgentCliAdapter
from curupira.models import CodexCliProfile, CodingTaskRequest


class CodexCliAdapter(CodingAgentCliAdapter):
    """Invoke Codex exec with an existing configuration profile and native effort setting."""

    executable = "codex"
    provider = "codex"

    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        """Build the native initial or resumed exec command with optional profile options."""
        profile = request.profile
        if not isinstance(profile, CodexCliProfile):
            raise TypeError("Codex requires a Codex profile")
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
