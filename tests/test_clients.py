"""Native argument translation, GitHub boundaries, and optional provider options."""

import json
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from typing_extensions import override

from opscli.agents import create_cli_adapter
from opscli.agents.base import CodingAgentCliAdapter
from opscli.clients.gh import GhClient
from opscli.clients.process import AsyncProcessRunner
from opscli.errors import (
    CliExecutionError,
    CliOutputError,
    UnsupportedCodingAgentError,
    WorkspacePathError,
)
from opscli.models import (
    ClaudeCodeCliProfile,
    CliProfile,
    CodexCliProfile,
    CodingTaskRequest,
    CommandRequest,
    GhIssueSearchRequest,
    GhPullRequestSearchRequest,
    GhRepositoryCloneRequest,
    OpenCodeCliProfile,
    ProcessResult,
)


class RecordingRunner(AsyncProcessRunner):
    """Simulate native stdout events and record literal argument vectors."""

    def __init__(self, *results: ProcessResult) -> None:
        self.results = list(results)
        self.requests: list[CommandRequest] = []

    @override
    async def run(
        self,
        request: CommandRequest,
        *,
        on_stdout_line: Callable[[str], Awaitable[None]] | None = None,
    ) -> ProcessResult:
        self.requests.append(request)
        result = self.results.pop(0)
        if on_stdout_line is not None:
            for line in result.stdout.splitlines():
                await on_stdout_line(line)
        return result


@pytest.mark.parametrize("provider", ["opencode", "codex", "claude"])
def test_factory_selects_native_provider_adapter(provider: str) -> None:
    assert isinstance(create_cli_adapter(provider), CodingAgentCliAdapter)


def test_factory_rejects_unknown_provider() -> None:
    with pytest.raises(UnsupportedCodingAgentError):
        create_cli_adapter("unknown")


@pytest.mark.parametrize(
    "profile", [OpenCodeCliProfile(), CodexCliProfile(), ClaudeCodeCliProfile()]
)
async def test_omitted_options_and_option_like_prompts_are_literal(
    tmp_path: Path, profile: CliProfile
) -> None:
    runner = RecordingRunner(ProcessResult(returncode=0))
    await create_cli_adapter(profile.provider, runner).run_task(
        CodingTaskRequest(cwd=tmp_path, profile=profile, message="--help; this is task data")
    )
    arguments = runner.requests[0].arguments
    assert arguments[-2:] == ("--", "--help; this is task data")
    assert not {
        "--agent",
        "--model",
        "--effort",
        "--variant",
        "--profile",
        "--mode",
        "--force",
        "--trust",
        "--auto",
        "--permission-mode",
    }.intersection(arguments)
    assert runner.requests[0].cwd == tmp_path


@pytest.mark.parametrize(
    ("profile", "flag", "value"),
    [
        (
            OpenCodeCliProfile(agent="custom-reviewer", model="vendor/model", effort="high"),
            "--agent",
            "custom-reviewer",
        ),
        (
            ClaudeCodeCliProfile(agent="custom-reviewer", model="sonnet", effort="high"),
            "--agent",
            "custom-reviewer",
        ),
        (CodexCliProfile(agent="work"), "--profile", "work"),
    ],
)
async def test_agent_option_uses_its_provider_native_flag(
    tmp_path: Path, profile: CliProfile, flag: str, value: str
) -> None:
    runner = RecordingRunner(ProcessResult(returncode=0))
    await create_cli_adapter(profile.provider, runner).run_task(
        CodingTaskRequest(cwd=tmp_path, profile=profile, message="Review")
    )
    arguments = runner.requests[0].arguments
    assert arguments[arguments.index(flag) + 1] == value


def test_provider_profiles_match_current_cli_argument_contracts(tmp_path: Path) -> None:
    requests = [
        (
            OpenCodeCliProfile(model="vendor/model", agent="reviewer", effort="high"),
            "opencode",
            (
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
            ),
        ),
        (
            CodexCliProfile(
                model="gpt-5.4",
                agent="work",
                effort="high",
                sandbox="workspace-write",
            ),
            "codex",
            (
                "exec",
                "resume",
                "native-session",
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
            ),
        ),
        (
            ClaudeCodeCliProfile(model="sonnet", agent="reviewer", effort="high"),
            "claude",
            (
                "-p",
                "--output-format",
                "stream-json",
                "--verbose",
                "--resume",
                "native-session",
                "--model",
                "sonnet",
                "--agent",
                "reviewer",
                "--effort",
                "high",
                "--",
                "Handle task",
            ),
        ),
    ]
    for profile, provider, expected in requests:
        arguments = create_cli_adapter(provider).build_arguments(
            CodingTaskRequest(
                cwd=tmp_path, profile=profile, session_id="native-session", message="Handle task"
            )
        )
        assert arguments == expected


def test_codex_exec_without_session_uses_json_config_and_profile(tmp_path: Path) -> None:
    profile = CodexCliProfile(
        model="gpt-5.4", agent="work", effort="ultra", sandbox="workspace-write"
    )

    arguments = create_cli_adapter("codex").build_arguments(
        CodingTaskRequest(cwd=tmp_path, profile=profile, message="Handle task")
    )

    assert arguments == (
        "exec",
        "--model",
        "gpt-5.4",
        "--profile",
        "work",
        "--config",
        'model_reasoning_effort="ultra"',
        "--sandbox",
        "workspace-write",
        "--json",
        "--",
        "Handle task",
    )


@pytest.mark.parametrize(
    ("profile", "event"),
    [
        (OpenCodeCliProfile(), '{"type":"text","sessionID":"native","part":{"text":"Done"}}'),
        (
            CodexCliProfile(),
            '{"type":"thread.started","thread_id":"native"}\n{"type":"item.completed","item":{"type":"agent_message","text":"Done"}}',
        ),
        (ClaudeCodeCliProfile(), '{"type":"result","session_id":"native","result":"Done"}'),
    ],
)
async def test_native_session_events_and_resume(
    tmp_path: Path, profile: CliProfile, event: str
) -> None:
    runner = RecordingRunner(
        ProcessResult(returncode=0, stdout="not JSON\n" + event + "\n" + event)
    )
    reported: list[str] = []

    async def callback(session_id: str) -> None:
        reported.append(session_id)

    result = await create_cli_adapter(profile.provider, runner).run_task(
        CodingTaskRequest(cwd=tmp_path, message="Continue", profile=profile, session_id="native"),
        on_session_started=callback,
    )
    assert reported == ["native"]
    assert "Done" in result.stdout
    assert "native" in runner.requests[0].arguments


def test_explicit_permission_options_are_provider_native(tmp_path: Path) -> None:
    profiles: list[CliProfile] = [
        OpenCodeCliProfile(auto_approve=True),
        ClaudeCodeCliProfile(permission_mode="dontAsk", permission_prompts="none"),
        CodexCliProfile(sandbox="workspace-write", auto_review=True, effort="high"),
    ]
    expected = ["--auto", "--permission-mode", "--sandbox"]
    for profile, flag in zip(profiles, expected, strict=True):
        arguments = create_cli_adapter(profile.provider).build_arguments(
            CodingTaskRequest(cwd=tmp_path, message="Work", profile=profile)
        )
        assert flag in arguments


async def test_github_query_is_not_shell_interpreted_and_json_is_validated() -> None:
    runner = RecordingRunner(
        ProcessResult(
            returncode=0,
            stdout='[{"number":42,"title":"Work","url":"https://github.com/acme/api/issues/42"}]',
        )
    )
    issues = await GhClient(runner).list_issues(
        GhIssueSearchRequest(repo="acme/api", query='label:"ready"; literal data')
    )
    assert issues[0].number == 42
    assert 'label:"ready"; literal data' in runner.requests[0].arguments


async def test_project_query_accepts_newline_json_and_requests_board_filter() -> None:
    output = "\n".join(
        json.dumps(
            {"number": number, "title": "Work", "url": "https://github.com/acme/api/issues/1"}
        )
        for number in (1, 2)
    )
    runner = RecordingRunner(ProcessResult(returncode=0, stdout=output))
    assert (
        len(
            await GhClient(runner).list_issues(
                GhIssueSearchRequest(repo="acme/api", query="is:open project:acme/9")
            )
        )
        == 2
    )
    arguments = runner.requests[0].arguments
    assert arguments[arguments.index("--state") + 1] == "open"
    assert "is:open project:acme/9" in arguments
    assert "--jq" in arguments
    assert arguments[arguments.index("--jq") + 1] == (
        '.[] | select(any(.projectItems[]?; .status.name == "Todo"))'
    )


async def test_pull_request_branch_metadata_is_preserved() -> None:
    runner = RecordingRunner(
        ProcessResult(
            returncode=0,
            stdout='[{"number":12,"title":"Review","url":"https://github.com/acme/api/pull/12","isDraft":true,"headRefName":"feature","baseRefName":"main"}]',
        )
    )
    pulls = await GhClient(runner).list_pull_requests(
        GhPullRequestSearchRequest(repo="acme/api", query="is:open")
    )
    assert pulls[0].is_draft
    assert pulls[0].head_ref_name == "feature"


@pytest.mark.parametrize("output", ["not JSON", "42", '[{"number":0}]'])
async def test_invalid_github_payloads_fail(output: str) -> None:
    with pytest.raises(CliOutputError):
        await GhClient(RecordingRunner(ProcessResult(returncode=0, stdout=output))).list_issues(
            GhIssueSearchRequest(repo="acme/api", query="is:open")
        )


async def test_nontransient_github_errors_are_not_retried() -> None:
    runner = RecordingRunner(ProcessResult(returncode=1, stderr="not authenticated"))
    with pytest.raises(CliExecutionError):
        await GhClient(runner).list_issues(GhIssueSearchRequest(repo="acme/api", query="is:open"))
    assert len(runner.requests) == 1


async def test_transient_github_errors_are_retried() -> None:
    runner = RecordingRunner(
        ProcessResult(returncode=1, stderr="HTTP 503"), ProcessResult(returncode=0, stdout="[]")
    )
    assert (
        await GhClient(runner).list_issues(GhIssueSearchRequest(repo="acme/api", query="is:open"))
        == []
    )
    assert len(runner.requests) == 2


async def test_existing_non_git_workspace_is_preserved(tmp_path: Path) -> None:
    runner = RecordingRunner()
    with pytest.raises(WorkspacePathError):
        await GhClient(runner).ensure_repository(
            GhRepositoryCloneRequest(repo="acme/api", destination=tmp_path)
        )
    assert not runner.requests
