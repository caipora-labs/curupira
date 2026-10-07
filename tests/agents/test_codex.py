"""Codex CLI argument translation tests."""

from pathlib import Path

from curupi.agents.codex import CodexCliAdapter
from curupi.models import CodexCliProfile, CodingTaskRequest


def test_codex_exec_arguments_preserve_profile_and_session(tmp_path: Path) -> None:
    profile = CodexCliProfile(
        model="gpt-5.4", agent="work", effort="high", sandbox="workspace-write"
    )
    request = CodingTaskRequest(
        cwd=tmp_path, profile=profile, session_id="session-1", message="Handle task"
    )

    assert CodexCliAdapter().build_arguments(request) == (
        "exec",
        "resume",
        "session-1",
        "--model",
        "gpt-5.4",
        "--profile",
        "work",
        "--config",
        'model_reasoning_effort="high"',
        "--sandbox",
        "workspace-write",
        "--json",
        "--",
        "Handle task",
    )


def test_codex_exec_arguments_without_optional_profile_values(tmp_path: Path) -> None:
    request = CodingTaskRequest(cwd=tmp_path, profile=CodexCliProfile(), message="Handle task")

    assert CodexCliAdapter().build_arguments(request) == (
        "exec",
        "--json",
        "--",
        "Handle task",
    )


def test_codex_auto_review_arguments(tmp_path: Path) -> None:
    request = CodingTaskRequest(
        cwd=tmp_path, profile=CodexCliProfile(auto_review=True), message="Review"
    )

    assert CodexCliAdapter().build_arguments(request) == (
        "exec",
        "--config",
        'approval_policy="on-request"',
        "--config",
        'approvals_reviewer="auto_review"',
        "--json",
        "--",
        "Review",
    )
