"""Typed adapter for the Codex CLI."""

from __future__ import annotations

import json

from gh_dispatch.clients.process import AsyncProcessRunner
from gh_dispatch.coding_agents import CodingAgent, SessionStartedCallback
from gh_dispatch.models import CodingTaskRequest, CommandRequest, ProcessResult


class CodexClient(CodingAgent):
    """Run Codex with JSONL events so sessions can be persisted and resumed."""

    def __init__(self, runner: AsyncProcessRunner | None = None) -> None:
        self._runner = runner or AsyncProcessRunner()

    async def run_task(
        self,
        request: CodingTaskRequest,
        *,
        on_session_started: SessionStartedCallback | None = None,
    ) -> ProcessResult:
        arguments: list[str] = []
        if request.agent is not None:
            arguments.extend(("--profile", request.agent))

        if request.session_id is None:
            arguments.extend(
                [
                    "exec",
                    "--json",
                    "--sandbox",
                    "workspace-write",
                    "--approve-for-me",
                ]
            )
        else:
            arguments.extend(("exec", "resume", request.session_id, "--json"))

        if request.model is not None:
            arguments.extend(("--model", request.model))
        if request.effort is not None:
            arguments.extend(("--config", f"model_reasoning_effort={json.dumps(request.effort)}"))
        arguments.append(request.message)

        command = CommandRequest(
            executable="codex",
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
        session_id = event.get("thread_id") if isinstance(event, dict) else None
        if isinstance(session_id, str) and session_id and session_id != reported_session_id:
            reported_session_id = session_id
            await callback(session_id)

    return handle


def _render_output(output: str) -> str:
    messages: list[str] = []
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "item.completed":
            continue
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "agent_message":
            text = item.get("text")
            if isinstance(text, str):
                messages.append(text)
    return "\n".join(messages)
