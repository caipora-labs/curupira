"""Qwen Code adapter argument, profile validation, and JSONL event behavior."""

from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from pydantic import ValidationError
from typing_extensions import override

from curupira.agents import create_cli_adapter
from curupira.providers.qwen import QwenCodeCliAdapter, QwenCodeCliProfile
from curupira.clients.process import AsyncProcessRunner
from curupira.models import CodingTaskRequest, CommandRequest, ProcessResult


class RecordingRunner(AsyncProcessRunner):
    """Record a Qwen Code invocation and emit configured JSONL output."""

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


def test_qwen_adapter_is_registered_and_builds_all_arguments_in_order(
    tmp_path: Path,
) -> None:
    request = CodingTaskRequest(
        cwd=tmp_path,
        profile=QwenCodeCliProfile(
            model="qwen3-coder-plus",
            approval_mode="auto-edit",
            max_session_turns=12,
        ),
        message="Resolve the issue",
    )

    adapter = create_cli_adapter("qwen")

    assert isinstance(adapter, QwenCodeCliAdapter)
    assert adapter.build_arguments(request) == (
        "--output-format",
        "stream-json",
        "--model",
        "qwen3-coder-plus",
        "--approval-mode",
        "auto-edit",
        "--max-session-turns",
        "12",
        "--prompt=Resolve the issue",
    )


def test_qwen_omits_unset_options_and_keeps_dash_prompt_as_one_argument(
    tmp_path: Path,
) -> None:
    request = CodingTaskRequest(
        cwd=tmp_path,
        profile=QwenCodeCliProfile(),
        message="-literal task prompt",
    )

    assert QwenCodeCliAdapter().build_arguments(request) == (
        "--output-format",
        "stream-json",
        "--prompt=-literal task prompt",
    )


def test_qwen_resumes_with_the_native_session_id(tmp_path: Path) -> None:
    request = CodingTaskRequest(
        cwd=tmp_path,
        profile=QwenCodeCliProfile(model="qwen3-coder-plus"),
        session_id="session-123",
        message="Continue",
    )

    assert QwenCodeCliAdapter().build_arguments(request) == (
        "--output-format",
        "stream-json",
        "--resume",
        "session-123",
        "--model",
        "qwen3-coder-plus",
        "--prompt=Continue",
    )


@pytest.mark.parametrize(
    "values",
    [
        {"agent": "reviewer"},
        {"effort": "high"},
        {"approval_mode": "auto_edit"},
        {"max_session_turns": 0},
        {"max_session_turns": True},
    ],
)
def test_qwen_rejects_unsupported_or_invalid_profile_values(values: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        QwenCodeCliProfile.model_validate(values)


async def test_qwen_reports_session_once_and_renders_documented_result(
    tmp_path: Path,
) -> None:
    fixture = Path(__file__).parent / "fixtures" / "qwen_stream.jsonl"
    output = fixture.read_text(encoding="utf-8")
    runner = RecordingRunner(output)
    adapter = create_cli_adapter("qwen", runner)
    reported: list[str] = []

    async def on_session_started(session_id: str) -> None:
        reported.append(session_id)

    result = await adapter.run_task(
        CodingTaskRequest(cwd=tmp_path, profile=QwenCodeCliProfile(), message="Continue"),
        on_session_started=on_session_started,
    )

    assert reported == ["qwen-session-123"]
    assert result.stdout == "Qwen task completed."
    assert runner.requests[0].executable == "qwen"
