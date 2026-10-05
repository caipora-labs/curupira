"""Contract tests for coding-agent adapters without installed agent CLIs."""

from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from typing_extensions import override

from gh_dispatch.agents.base import CodingAgentCliAdapter
from gh_dispatch.clients.process import AsyncProcessRunner
from gh_dispatch.errors import UnsupportedCodingAgentError
from gh_dispatch.models import (
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
