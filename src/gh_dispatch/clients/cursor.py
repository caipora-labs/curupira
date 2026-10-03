"""Typed adapter for the Cursor Agent CLI."""

from __future__ import annotations

import json

from gh_dispatch.clients.process import AsyncProcessRunner
from gh_dispatch.coding_agents import CodingAgent, SessionStartedCallback
from gh_dispatch.models import CodingTaskRequest, CommandRequest, ProcessResult


class CursorCliClient(CodingAgent):
    """Run Cursor Agent in print mode and resume saved chats by ID."""

    def __init__(self, runner: AsyncProcessRunner | None = None) -> None:
        self._runner = runner or AsyncProcessRunner()

    async def run_task(
        self,
        request: CodingTaskRequest,
        *,
        on_session_started: SessionStartedCallback | None = None,
    ) -> ProcessResult:
        arguments = [
            "-p",
            "--force",
            "--trust",
            "--output-format",
            "stream-json",
        ]
        if request.session_id is not None:
            arguments.extend(("--resume", request.session_id))
        if request.model is not None:
            arguments.extend(("--model", request.model))
        if request.agent in {"ask", "plan"}:
            arguments.extend(("--mode", request.agent))
        arguments.append(request.message)

        command = CommandRequest(
            executable="agent",
            arguments=tuple(arguments),
            cwd=request.cwd,
            timeout=None,
            capture_output=True,
        )
        if on_session_started is None:
            result = await self._runner.run(command)
        else:
            result = await self._runner.run(
                command,
                on_stdout_line=_session_event_handler(on_session_started),
            )
        return result.model_copy(update={"stdout": _render_output(result.stdout)})


def _session_event_handler(callback: SessionStartedCallback):
    reported_session_id: str | None = None

    async def handle(line: str) -> None:
        nonlocal reported_session_id
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return
        session_id = event.get("session_id") if isinstance(event, dict) else None
        if isinstance(session_id, str) and session_id and reported_session_id is None:
            reported_session_id = session_id
            await callback(session_id)

    return handle


def _render_output(output: str) -> str:
    result_text: str | None = None
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("type") == "result":
            result = event.get("result")
            if isinstance(result, str):
                result_text = result
    return result_text if result_text is not None else ""
