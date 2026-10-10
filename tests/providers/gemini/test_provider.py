"""Gemini CLI argument translation, sessions, and stream rendering."""

from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from pydantic import ValidationError
from typing_extensions import override

from curupira.agents import create_cli_adapter
from curupira.providers.gemini import GeminiCliAdapter, GeminiCliProfile
from curupira.clients.process import AsyncProcessRunner
from curupira.models import CodingTaskRequest, CommandRequest, ProcessResult


class RecordingRunner(AsyncProcessRunner):
    """Record a Gemini invocation and emit configured JSONL output."""

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


def test_gemini_adapter_is_registered_and_maps_all_options_in_order(tmp_path: Path) -> None:
    request = CodingTaskRequest(
        cwd=tmp_path,
        profile=GeminiCliProfile(
            model="gemini-2.5-pro", approval_mode="auto_edit", skip_trust=True
        ),
        message="Handle task",
    )

    adapter = create_cli_adapter("gemini")

    assert isinstance(adapter, GeminiCliAdapter)
    assert adapter.build_arguments(request) == (
        "--output-format",
        "stream-json",
        "--model",
        "gemini-2.5-pro",
        "--approval-mode",
        "auto_edit",
        "--skip-trust",
        "--prompt=Handle task",
    )


def test_gemini_adapter_omits_unset_options(tmp_path: Path) -> None:
    request = CodingTaskRequest(cwd=tmp_path, profile=GeminiCliProfile(), message="Handle task")

    assert GeminiCliAdapter().build_arguments(request) == (
        "--output-format",
        "stream-json",
        "--prompt=Handle task",
    )


def test_gemini_adapter_resumes_native_session(tmp_path: Path) -> None:
    request = CodingTaskRequest(
        cwd=tmp_path,
        profile=GeminiCliProfile(),
        session_id="session-123",
        message="Continue",
    )

    assert GeminiCliAdapter().build_arguments(request) == (
        "--output-format",
        "stream-json",
        "--resume",
        "session-123",
        "--prompt=Continue",
    )


def test_gemini_prompt_starting_with_dash_is_one_argument(tmp_path: Path) -> None:
    request = CodingTaskRequest(
        cwd=tmp_path, profile=GeminiCliProfile(), message="--help is task text"
    )

    assert GeminiCliAdapter().build_arguments(request)[-1] == "--prompt=--help is task text"


@pytest.mark.parametrize("field", ["agent", "effort"])
def test_gemini_profile_rejects_unsupported_fields(field: str) -> None:
    with pytest.raises(ValidationError, match=field):
        GeminiCliProfile.model_validate({field: "unsupported"})


def test_gemini_profile_rejects_unknown_approval_mode() -> None:
    with pytest.raises(ValidationError, match="approval_mode"):
        GeminiCliProfile.model_validate({"approval_mode": "unsafe"})


async def test_gemini_run_task_reports_init_session_once(tmp_path: Path) -> None:
    runner = RecordingRunner(
        '{"type":"init","session_id":"gemini-session"}\n'
        '{"type":"init","session_id":"gemini-session"}'
    )
    adapter = create_cli_adapter("gemini", runner)
    reported: list[str] = []

    async def on_session_started(session_id: str) -> None:
        reported.append(session_id)

    result = await adapter.run_task(
        CodingTaskRequest(cwd=tmp_path, profile=GeminiCliProfile(), message="Run"),
        on_session_started=on_session_started,
    )

    assert reported == ["gemini-session"]
    assert runner.requests[0].executable == "gemini"
    assert result.stdout == ""


def test_gemini_render_output_returns_only_assistant_messages() -> None:
    fixture = Path(__file__).parent / "fixtures" / "gemini_stream.jsonl"

    rendered = GeminiCliAdapter().render_output(fixture.read_text(encoding="utf-8"))

    assert rendered == "Gemini responded.\nContinued after tool."
