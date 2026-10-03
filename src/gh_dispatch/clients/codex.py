"""Native Codex CLI argument translation."""

import json

from gh_dispatch.coding_agents import CodingAgentCliAdapter
from gh_dispatch.models import CodexCliProfile, CodingTaskRequest


class CodexCliAdapter(CodingAgentCliAdapter):
    """Invoke Codex exec; configuration profiles are not custom agents."""

    executable = "codex"
    provider = "codex"

    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        """Apply global native options before initial or resumed exec commands."""
        profile = request.profile
        if not isinstance(profile, CodexCliProfile):
            raise ValueError("Codex requires a Codex profile")
        arguments: list[str] = []
        if profile.model is not None:
            arguments.extend(("--model", profile.model))
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
        arguments.append("exec")
        if request.session_id is not None:
            arguments.extend(("resume", request.session_id))
        return (*arguments, "--json", "--", request.message)
