"""Typed asynchronous client for the OpenCode CLI."""

from __future__ import annotations

import json

from gh_dispatch.clients.process import AsyncProcessRunner
from gh_dispatch.coding_agents import CodingAgent, SessionStartedCallback
from gh_dispatch.models import CodingTaskRequest, CommandRequest, ProcessResult


class OpenCodeClient(CodingAgent):
    """Run an OpenCode task non-interactively so multiple workers can coexist."""

    def __init__(self, runner: AsyncProcessRunner | None = None) -> None:
        self._runner = runner or AsyncProcessRunner()

    async def run_task(
        self,
        request: CodingTaskRequest,
        *,
        on_session_started: SessionStartedCallback | None = None,
    ) -> ProcessResult:
        arguments = ["run", "--format", "json"]
        if request.session_id is not None:
            arguments.extend(("--session", request.session_id))
        if request.model is not None:
            arguments.extend(("--model", request.model))
        if request.agent is not None:
            arguments.extend(("--agent", request.agent))
        if request.effort is not None:
            arguments.extend(("--variant", request.effort))
        arguments.append(request.message)

        command = CommandRequest(
            executable="opencode",
            arguments=tuple(arguments),
            cwd=request.cwd,
            timeout=None,
            capture_output=True,
        )
        if on_session_started is None:
            result = await self._runner.run(command)
            return result.model_copy(update={"stdout": _render_json_output(result.stdout)})

        reported_session_id: str | None = None

        async def handle_event(line: str) -> None:
            nonlocal reported_session_id
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                return
            session_id = event.get("sessionID") if isinstance(event, dict) else None
            if isinstance(session_id, str) and session_id and session_id != reported_session_id:
                reported_session_id = session_id
                await on_session_started(session_id)

        result = await self._runner.run(command, on_stdout_line=handle_event)
        return result.model_copy(update={"stdout": _render_json_output(result.stdout)})


def _render_json_output(output: str) -> str:
    """Keep assistant text while hiding the raw JSON event stream from callers."""
    text_parts: list[str] = []
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "text":
            continue
        part = event.get("part")
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            text_parts.append(part["text"])
    return "\n".join(text_parts)
