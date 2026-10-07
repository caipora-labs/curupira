"""Claude Code adapter argument translation."""

from pathlib import Path

import pytest

from curupi.agents.claude import ClaudeCodeCliAdapter
from curupi.models import ClaudeCodeCliProfile, CodingTaskRequest


def test_build_arguments_uses_claude_native_options(tmp_path: Path) -> None:
    request = CodingTaskRequest(
        cwd=tmp_path,
        profile=ClaudeCodeCliProfile(
            model="sonnet",
            agent="reviewer",
            effort="high",
            permission_mode="dontAsk",
            permission_prompts="none",
        ),
        session_id="session-123",
        message="Review this change",
    )

    assert ClaudeCodeCliAdapter().build_arguments(request) == (
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--resume",
        "session-123",
        "--model",
        "sonnet",
        "--agent",
        "reviewer",
        "--effort",
        "high",
        "--permission-mode",
        "dontAsk",
        "--permission-prompts",
        "none",
        "--",
        "Review this change",
    )


def test_build_arguments_keeps_prompt_literal_and_omits_missing_options(tmp_path: Path) -> None:
    request = CodingTaskRequest(
        cwd=tmp_path,
        profile=ClaudeCodeCliProfile(),
        message="--help; task data",
    )

    assert ClaudeCodeCliAdapter().build_arguments(request) == (
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--",
        "--help; task data",
    )


def test_build_arguments_rejects_non_claude_profile(tmp_path: Path) -> None:
    from curupi.models import CodexCliProfile

    request = CodingTaskRequest(cwd=tmp_path, profile=CodexCliProfile(), message="Review")

    with pytest.raises(ValueError, match="Claude Code requires a Claude profile"):
        ClaudeCodeCliAdapter().build_arguments(request)
