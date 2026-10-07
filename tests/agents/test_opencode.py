"""OpenCode CLI argument translation tests."""

from pathlib import Path

from opscli.agents.opencode import OpenCodeCliAdapter
from opscli.models import CodingTaskRequest, OpenCodeCliProfile


def test_opencode_arguments_preserve_session_and_profile(tmp_path: Path) -> None:
    request = CodingTaskRequest(
        cwd=tmp_path,
        profile=OpenCodeCliProfile(model="vendor/model", agent="reviewer", effort="high"),
        session_id="native-session",
        message="Handle task",
    )

    assert OpenCodeCliAdapter().build_arguments(request) == (
        "run",
        "--format",
        "json",
        "--session",
        "native-session",
        "--model",
        "vendor/model",
        "--agent",
        "reviewer",
        "--variant",
        "high",
        "--",
        "Handle task",
    )


def test_opencode_arguments_without_options_and_with_auto_approve(tmp_path: Path) -> None:
    request = CodingTaskRequest(
        cwd=tmp_path, profile=OpenCodeCliProfile(auto_approve=True), message="Review"
    )

    assert OpenCodeCliAdapter().build_arguments(request) == (
        "run",
        "--format",
        "json",
        "--auto",
        "--",
        "Review",
    )
