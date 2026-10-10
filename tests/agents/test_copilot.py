"""GitHub Copilot CLI adapter argument translation and session behavior."""

from collections.abc import Awaitable, Callable
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError
from typing_extensions import override

from curupira.agents import create_cli_adapter
from curupira.agents.copilot import CopilotCliAdapter, CopilotCliProfile
from curupira.clients.process import AsyncProcessRunner
from curupira.models import (
    ClaudeCodeCliProfile,
    CodingTaskRequest,
    CommandRequest,
    ProcessResult,
)


class RecordingRunner(AsyncProcessRunner):
    """Record a Copilot invocation and emit configured output lines."""

    def __init__(self, output: str = "") -> None:
        self.output = output
        self.requests: list[CommandRequest] = []

    @override
    async def run(
        self,
        request: CommandRequest,
        *,
        on_stdout_line: Callable[[str], Awaitable[None]] | None = None,
    ) -> ProcessResult:
        self.requests.append(request)
        if on_stdout_line is not None:
            for line in self.output.splitlines():
                await on_stdout_line(line)
        return ProcessResult(returncode=0, stdout=self.output)


def test_copilot_adapter_is_registered_and_builds_all_profile_arguments(
    tmp_path: Path,
) -> None:
    profile = CopilotCliProfile(
        model="claude-sonnet-4.5",
        agent="issue-resolver",
        effort="xhigh",
        allow_all_tools=True,
        allow_tools=("shell(git:*)", "write"),
        deny_tools=("shell(rm:*)",),
    )
    request = CodingTaskRequest(
        cwd=tmp_path,
        profile=profile,
        new_session_id="b59a5fdc-2c40-4a30-a353-d5cad2f1f601",
        message="Resolve the issue",
    )

    adapter = create_cli_adapter("copilot")

    assert isinstance(adapter, CopilotCliAdapter)
    assert adapter.build_arguments(request) == (
        "--output-format=json",
        "--no-ask-user",
        "--session-id=b59a5fdc-2c40-4a30-a353-d5cad2f1f601",
        "--model=claude-sonnet-4.5",
        "--agent=issue-resolver",
        "--reasoning-effort=xhigh",
        "--allow-all-tools",
        "--allow-tool=shell(git:*),write",
        "--deny-tool=shell(rm:*)",
        "--prompt=Resolve the issue",
    )


def test_copilot_arguments_without_profile_options_use_new_session_id(tmp_path: Path) -> None:
    request = CodingTaskRequest(
        cwd=tmp_path,
        profile=CopilotCliProfile(),
        new_session_id="new-session-id",
        message="Review",
    )

    assert CopilotCliAdapter().build_arguments(request) == (
        "--output-format=json",
        "--no-ask-user",
        "--session-id=new-session-id",
        "--prompt=Review",
    )


def test_copilot_resumes_with_session_id_and_preserves_leading_dash_prompt(
    tmp_path: Path,
) -> None:
    request = CodingTaskRequest(
        cwd=tmp_path,
        profile=CopilotCliProfile(),
        session_id="persisted-session-id",
        message="--review this literal task",
    )

    arguments = CopilotCliAdapter().build_arguments(request)

    assert arguments == (
        "--output-format=json",
        "--no-ask-user",
        "--session-id=persisted-session-id",
        "--prompt=--review this literal task",
    )
    assert "--resume" not in arguments


def test_copilot_profile_rejects_unknown_effort() -> None:
    with pytest.raises(ValidationError, match="effort"):
        CopilotCliProfile.model_validate({"effort": "ultra"})


@pytest.mark.parametrize("field", ["allow_tools", "deny_tools"])
def test_copilot_profile_rejects_comma_in_tool_entries(field: str) -> None:
    with pytest.raises(ValidationError, match="must not contain commas"):
        CopilotCliProfile.model_validate({field: ("shell(git:*,write)",)})


def test_copilot_adapter_rejects_non_copilot_profile(tmp_path: Path) -> None:
    request = CodingTaskRequest(
        cwd=tmp_path,
        profile=ClaudeCodeCliProfile(),
        session_id="persisted-session-id",
        message="Review",
    )

    with pytest.raises(ValueError, match="requires a Copilot profile"):
        CopilotCliAdapter().build_arguments(request)


async def test_copilot_run_task_reports_and_passes_preassigned_uuid(tmp_path: Path) -> None:
    runner = RecordingRunner()
    adapter = CopilotCliAdapter(runner)
    reported: list[str] = []

    async def on_session_started(session_id: str) -> None:
        reported.append(session_id)

    await adapter.run_task(
        CodingTaskRequest(cwd=tmp_path, profile=CopilotCliProfile(), message="Continue"),
        on_session_started=on_session_started,
    )

    assert len(reported) == 1
    assert str(UUID(reported[0])) == reported[0]
    assert runner.requests[0].executable == "copilot"
    assert runner.requests[0].arguments[2] == f"--session-id={reported[0]}"


def test_copilot_render_output_returns_raw_jsonl_unchanged() -> None:
    output = '{"type":"assistant.message","content":"Done"}\n{"type":"session.end"}\n'

    assert CopilotCliAdapter().render_output(output) == output
