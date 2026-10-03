"""Typed adapter for Claude Code CLI."""

from __future__ import annotations

import json

from gh_dispatch.clients.process import AsyncProcessRunner
from gh_dispatch.coding_agents import CodingAgent, SessionStartedCallback
from gh_dispatch.models import CodingTaskRequest, CommandRequest, ProcessResult


class ClaudeCodeClient(CodingAgent):
    """Run Claude Code in print mode with a resumable JSON event stream."""

    def __init__(self, runner: AsyncProcessRunner | None = None) -> None:
        self._runner = runner or AsyncProcessRunner()

    async def run_task(
        self,
        request: CodingTaskRequest,
        *,
        on_session_started: SessionStartedCallback | None = None,
    ) -> ProcessResult:
        arguments = ["-p", request.message]
        if request.session_id is not None:
            arguments.extend(("--resume", request.session_id))
        arguments.extend(
            (
                "--output-format",
                "stream-json",
                "--verbose",
                "--permission-mode",
                "auto",
                "--permission-prompts",
                "none",
            )
        )
        if request.model is not None:
            arguments.extend(("--model", request.model))
        if request.agent is not None:
            arguments.extend(("--agent", request.agent))
        if request.effort is not None:
            arguments.extend(("--effort", request.effort))

        command = CommandRequest(
            executable="claude",
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
        if isinstance(session_id, str) and session_id and session_id != reported_session_id:
            reported_session_id = session_id
            await callback(session_id)

    return handle


def _render_output(output: str) -> str:
    final_result: str | None = None
    assistant_messages: list[str] = []
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("type") == "result" and isinstance(event.get("result"), str):
            final_result = event["result"]
        elif event.get("type") == "assistant":
            message = event.get("message")
            content = message.get("content") if isinstance(message, dict) else None
            if isinstance(content, list):
                assistant_messages.extend(
                    part["text"]
                    for part in content
                    if isinstance(part, dict)
                    and part.get("type") == "text"
                    and isinstance(part.get("text"), str)
                )
    return final_result if final_result is not None else "\n".join(assistant_messages)
