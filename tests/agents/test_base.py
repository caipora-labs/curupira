"""Contract tests for coding-agent adapters without installed agent CLIs."""

from collections.abc import Awaitable, Callable
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel
from typing_extensions import override

from curupira.agents.base import CodingAgentCliAdapter
from curupira.clients.process import AsyncProcessRunner
from curupira.errors import UnsupportedCodingAgentError
from curupira.models import (
    CliProfile,
    CodexCliProfile,
    CodingTaskRequest,
    CommandRequest,
    OpenCodeCliProfile,
    ProcessResult,
)


class FakeRunner(AsyncProcessRunner):
    """Emit configured JSONL output through the runner callback."""

    def __init__(self, output: str) -> None:
        self.output = output

    @override
    async def run(
        self,
        request: CommandRequest,
        *,
        on_stdout_line: Callable[[str], Awaitable[None]] | None = None,
    ) -> ProcessResult:
        if on_stdout_line is not None:
            for line in self.output.splitlines():
                await on_stdout_line(line)
        return ProcessResult(returncode=0, stdout=self.output)


class FakeAdapter(CodingAgentCliAdapter):
    """Adapter with deterministic executable and arguments."""

    executable = "fake-agent"
    provider = "opencode"

    @override
    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        return (request.message,)


def request(path: Path, profile: CliProfile | None = None) -> CodingTaskRequest:
    """Build a minimal fake task request."""
    return CodingTaskRequest(
        cwd=path, profile=profile or OpenCodeCliProfile(), message="Do the task"
    )


def test_adapter_requires_build_arguments() -> None:
    with pytest.raises(TypeError, match="abstract"):
        CodingAgentCliAdapter()  # type: ignore[abstract]


async def test_run_task_rejects_profile_for_another_provider(tmp_path: Path) -> None:
    adapter = FakeAdapter(FakeRunner(""))
    with pytest.raises(UnsupportedCodingAgentError):
        await adapter.run_task(request(tmp_path, profile=CodexCliProfile()))


async def test_run_task_reports_each_distinct_session_once(tmp_path: Path) -> None:
    output = (
        '{"type":"thread.started","thread_id":"first"}\n'
        '{"type":"thread.started","thread_id":"second"}\n'
        '{"type":"thread.started","thread_id":"first"}'
    )
    adapter = FakeAdapter(FakeRunner(output))
    reported: list[str] = []

    async def callback(session_id: str) -> None:
        reported.append(session_id)

    await adapter.run_task(request(tmp_path), on_session_started=callback)
    assert reported == ["first", "second"]


class RecordingRunner(FakeRunner):
    """Record each process start in a shared call log."""

    def __init__(self, output: str, calls: list[str]) -> None:
        super().__init__(output)
        self.calls = calls

    @override
    async def run(
        self,
        request: CommandRequest,
        *,
        on_stdout_line: Callable[[str], Awaitable[None]] | None = None,
    ) -> ProcessResult:
        self.calls.append("run")
        return await super().run(request, on_stdout_line=on_stdout_line)


class SessionHeader(BaseModel):
    """Session header record emitted by the fake CLI."""

    type: str = ""
    id: str | None = None


class HeaderSessionAdapter(FakeAdapter):
    """Read the session from a pi-style ``{"type":"session","id":...}`` header."""

    @override
    def session_id_from_line(self, line: str) -> str | None:
        header = SessionHeader.model_validate_json(line)
        return header.id if header.type == "session" else None


class AssigningAdapter(FakeAdapter):
    """Opt into pre-assigned session identifiers and record built requests."""

    assigns_session_id = True

    def __init__(self, runner: AsyncProcessRunner, calls: list[str]) -> None:
        super().__init__(runner)
        self.calls = calls
        self.requests: list[CodingTaskRequest] = []

    @override
    def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
        self.calls.append("build_arguments")
        self.requests.append(request)
        return super().build_arguments(request)


async def test_overridden_session_hook_reports_header_session_once(tmp_path: Path) -> None:
    output = '{"type":"session","id":"x"}\n{"type":"message"}\n{"type":"session","id":"x"}'
    adapter = HeaderSessionAdapter(FakeRunner(output))
    reported: list[str] = []

    async def callback(session_id: str) -> None:
        reported.append(session_id)

    await adapter.run_task(request(tmp_path), on_session_started=callback)
    assert reported == ["x"]


async def test_assigned_session_is_reported_before_the_process_starts(tmp_path: Path) -> None:
    calls: list[str] = []
    adapter = AssigningAdapter(RecordingRunner("", calls), calls)

    async def callback(session_id: str) -> None:
        calls.append(f"started:{session_id}")

    await adapter.run_task(request(tmp_path), on_session_started=callback)
    new_session_id = adapter.requests[0].new_session_id
    assert new_session_id is not None
    assert str(UUID(new_session_id)) == new_session_id
    assert adapter.requests[0].session_id is None
    assert calls == [f"started:{new_session_id}", "build_arguments", "run"]


async def test_assigned_session_is_not_reported_again_when_echoed(tmp_path: Path) -> None:
    calls: list[str] = []
    runner = RecordingRunner("", calls)
    adapter = AssigningAdapter(runner, calls)
    reported: list[str] = []

    async def callback(session_id: str) -> None:
        reported.append(session_id)
        runner.output = f'{{"type":"init","session_id":"{session_id}"}}'

    await adapter.run_task(request(tmp_path), on_session_started=callback)
    assert reported == [adapter.requests[0].new_session_id]


async def test_resumed_run_does_not_assign_a_session(tmp_path: Path) -> None:
    calls: list[str] = []
    adapter = AssigningAdapter(RecordingRunner("", calls), calls)
    reported: list[str] = []

    async def callback(session_id: str) -> None:
        reported.append(session_id)

    resumed = request(tmp_path).model_copy(update={"session_id": "existing"})
    await adapter.run_task(resumed, on_session_started=callback)
    assert adapter.requests[0].session_id == "existing"
    assert adapter.requests[0].new_session_id is None
    assert reported == []


@pytest.mark.parametrize("field", ["sessionID", "session_id", "thread_id"])
def test_default_session_hook_reads_built_in_aliases(field: str) -> None:
    adapter = FakeAdapter(FakeRunner(""))
    assert adapter.session_id_from_line(f'{{"type":"start","{field}":"abc"}}') == "abc"


def test_default_session_hook_ignores_non_event_lines() -> None:
    adapter = FakeAdapter(FakeRunner(""))
    assert adapter.session_id_from_line("plain text") is None
    assert adapter.session_id_from_line('{"type":"text"}') is None


def test_render_output_extracts_supported_event_text() -> None:
    adapter = FakeAdapter(FakeRunner(""))
    output = "\n".join(
        (
            '{"type":"text","part":{"text":"OpenCode text"}}',
            '{"type":"item.completed","item":{"type":"agent_message","text":"Codex text"}}',
            '{"type":"result","result":"Claude text"}',
        )
    )
    assert adapter.render_output(output) == "OpenCode text\nCodex text\nClaude text"
