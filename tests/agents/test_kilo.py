"""Kilo CLI argument translation and JSONL behavior tests."""

from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from typing_extensions import override

from curupira.agents.kilo import KiloCliAdapter, KiloCliProfile
from curupira.clients.process import AsyncProcessRunner
from curupira.errors import UnsupportedCodingAgentError
from curupira.models import CodingTaskRequest, CommandRequest, OpenCodeCliProfile, ProcessResult


class FakeRunner(AsyncProcessRunner):
    """Emit fixture JSONL without invoking an installed CLI."""

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


def make_request(
    path: Path,
    *,
    profile: KiloCliProfile | OpenCodeCliProfile | None = None,
    session_id: str | None = None,
    message: str = "Handle task",
) -> CodingTaskRequest:
    """Build a Kilo task request, optionally with a deliberately foreign profile."""
    return CodingTaskRequest(
        cwd=path,
        profile=profile or KiloCliProfile(),
        session_id=session_id,
        message=message,
    )


def test_kilo_arguments_preserve_all_profile_options(tmp_path: Path) -> None:
    request = make_request(
        tmp_path,
        profile=KiloCliProfile(
            model="anthropic/claude-sonnet-4",
            agent="reviewer",
            effort="high",
            auto_approve=True,
        ),
    )

    assert KiloCliAdapter().build_arguments(request) == (
        "run",
        "--format",
        "json",
        "--model",
        "anthropic/claude-sonnet-4",
        "--agent",
        "reviewer",
        "--variant",
        "high",
        "--auto",
        "--",
        "Handle task",
    )


def test_kilo_arguments_omit_unset_options(tmp_path: Path) -> None:
    assert KiloCliAdapter().build_arguments(make_request(tmp_path)) == (
        "run",
        "--format",
        "json",
        "--",
        "Handle task",
    )


def test_kilo_arguments_resume_session_before_profile_options(tmp_path: Path) -> None:
    request = make_request(
        tmp_path,
        profile=KiloCliProfile(model="openai/gpt-5", effort="max"),
        session_id="ses_123abc",
    )

    assert KiloCliAdapter().build_arguments(request) == (
        "run",
        "--format",
        "json",
        "--session",
        "ses_123abc",
        "--model",
        "openai/gpt-5",
        "--variant",
        "max",
        "--",
        "Handle task",
    )


def test_kilo_message_starting_with_dash_follows_separator(tmp_path: Path) -> None:
    assert KiloCliAdapter().build_arguments(make_request(tmp_path, message="-please review")) == (
        "run",
        "--format",
        "json",
        "--",
        "-please review",
    )


def test_kilo_adapter_rejects_non_kilo_profile(tmp_path: Path) -> None:
    request = make_request(tmp_path, profile=OpenCodeCliProfile())

    with pytest.raises(ValueError, match="Kilo profile"):
        KiloCliAdapter().build_arguments(request)


async def test_kilo_run_reports_session_once_and_renders_text_parts(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "fixtures" / "kilo_json.jsonl"
    output = fixture.read_text(encoding="utf-8")
    adapter = KiloCliAdapter(FakeRunner(output))
    reported: list[str] = []

    async def on_session_started(session_id: str) -> None:
        reported.append(session_id)

    result = await adapter.run_task(make_request(tmp_path), on_session_started=on_session_started)

    assert reported == ["ses_kilo123"]
    assert result.stdout == "First response.\nSecond response."


async def test_kilo_run_rejects_profile_from_another_provider(tmp_path: Path) -> None:
    adapter = KiloCliAdapter(FakeRunner(""))

    with pytest.raises(UnsupportedCodingAgentError, match="cannot use opencode profile"):
        await adapter.run_task(make_request(tmp_path, profile=OpenCodeCliProfile()))
