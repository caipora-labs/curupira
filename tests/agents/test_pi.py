"""pi adapter argument, profile validation, and JSONL event behavior."""

from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from pydantic import ValidationError
from typing_extensions import override

from curupira.agents.pi import PiCliAdapter, PiCliProfile
from curupira.clients.process import AsyncProcessRunner
from curupira.models import CodingTaskRequest, CommandRequest, ProcessResult


class RecordingRunner(AsyncProcessRunner):
    """Record a pi invocation and emit configured JSONL output."""

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


def test_pi_builds_arguments_in_native_option_order(tmp_path: Path) -> None:
    request = CodingTaskRequest(
        cwd=tmp_path,
        profile=PiCliProfile(
            model="anthropic/claude-sonnet-4",
            model_provider="anthropic",
            effort="high",
            tools=("read", "edit"),
            exclude_tools=("bash", "write"),
            approve=True,
        ),
        message="Resolve the issue",
    )

    assert PiCliAdapter().build_arguments(request) == (
        "--mode",
        "json",
        "--provider",
        "anthropic",
        "--model",
        "anthropic/claude-sonnet-4",
        "--thinking",
        "high",
        "--tools",
        "read,edit",
        "--exclude-tools",
        "bash,write",
        "--approve",
        "--",
        "Resolve the issue",
    )


def test_pi_omits_unset_arguments_and_places_dash_prompt_after_separator(
    tmp_path: Path,
) -> None:
    request = CodingTaskRequest(cwd=tmp_path, profile=PiCliProfile(), message="-literal prompt")

    assert PiCliAdapter().build_arguments(request) == (
        "--mode",
        "json",
        "--",
        "-literal prompt",
    )


def test_pi_resumes_with_the_native_session_id(tmp_path: Path) -> None:
    request = CodingTaskRequest(
        cwd=tmp_path,
        profile=PiCliProfile(model="anthropic/claude-sonnet-4"),
        session_id="session-123",
        message="Continue",
    )

    assert PiCliAdapter().build_arguments(request) == (
        "--mode",
        "json",
        "--session",
        "session-123",
        "--model",
        "anthropic/claude-sonnet-4",
        "--",
        "Continue",
    )


@pytest.mark.parametrize(
    "values",
    [
        {"model_provider": "anthropic"},
        {"agent": "x"},
        {"effort": "ultra"},
    ],
)
def test_pi_rejects_invalid_profile_values(values: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        PiCliProfile.model_validate(values)


async def test_pi_reports_session_header_once(tmp_path: Path) -> None:
    header = '{"type":"session","version":3,"id":"pi-session"}'
    runner = RecordingRunner(f"{header}\n{header}")
    adapter = PiCliAdapter(runner)
    reported: list[str] = []

    async def on_session_started(session_id: str) -> None:
        reported.append(session_id)

    await adapter.run_task(
        CodingTaskRequest(cwd=tmp_path, profile=PiCliProfile(), message="Do the task"),
        on_session_started=on_session_started,
    )

    assert reported == ["pi-session"]
    assert adapter.session_id_from_line(header) == "pi-session"


def test_pi_renders_only_assistant_text_blocks_from_json_fixture() -> None:
    fixture = Path(__file__).parent / "fixtures" / "pi_json.jsonl"

    assert PiCliAdapter().render_output(fixture.read_text(encoding="utf-8")) == (
        "The result is ready.\nHere are the details."
    )
