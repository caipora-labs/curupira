"""Cursor adapter argument translation and session event behavior."""

from collections.abc import Awaitable, Callable
from pathlib import Path

from typing_extensions import override

from curupira.agents import create_cli_adapter
from curupira.providers.cursor import CursorCliAdapter
from curupira.clients.process import AsyncProcessRunner
from curupira.models import (
    CodingTaskRequest,
    CommandRequest,
    CursorCliProfile,
    ProcessResult,
)


class RecordingRunner(AsyncProcessRunner):
    """Record a Cursor invocation and emit configured output lines."""

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


def test_cursor_adapter_is_registered_and_preserves_native_arguments(tmp_path: Path) -> None:
    profile = CursorCliProfile(model="composer-2.5", agent="plan", force=True, trust=True)
    request = CodingTaskRequest(
        cwd=tmp_path, profile=profile, session_id="native-session", message="Handle task"
    )

    adapter = create_cli_adapter("cursor")

    assert isinstance(adapter, CursorCliAdapter)
    assert adapter.build_arguments(request) == (
        "--print",
        "--output-format",
        "stream-json",
        "--resume",
        "native-session",
        "--mode",
        "plan",
        "--model",
        "composer-2.5",
        "--force",
        "--trust",
        "--",
        "Handle task",
    )


async def test_cursor_adapter_reports_session_and_renders_result(tmp_path: Path) -> None:
    runner = RecordingRunner('{"type":"result","session_id":"native-session","result":"Done"}')
    adapter = create_cli_adapter("cursor", runner)
    reported: list[str] = []

    async def on_session_started(session_id: str) -> None:
        reported.append(session_id)

    result = await adapter.run_task(
        CodingTaskRequest(cwd=tmp_path, profile=CursorCliProfile(), message="Continue"),
        on_session_started=on_session_started,
    )

    assert reported == ["native-session"]
    assert result.stdout == "Done"
    assert runner.requests[0].executable == "agent"


def test_cursor_prompt_is_passed_as_literal_task_data(tmp_path: Path) -> None:
    request = CodingTaskRequest(
        cwd=tmp_path,
        profile=CursorCliProfile(),
        message="--help; literal task data",
    )

    arguments = create_cli_adapter("cursor").build_arguments(request)

    assert arguments[-2:] == ("--", "--help; literal task data")
