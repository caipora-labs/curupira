"""Interactive launch specs: argv recipes, PTY env allowlist, and availability."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from typing_extensions import override

from curupira.agents.assistant import resolve_assistant_model
from curupira.agents.base import CodingAgentCliAdapter
from curupira.agents.interactive import InteractiveLaunchSpec, default_pty_env, spec_available
from curupira.agents.registry import registered
from curupira.models import (
    ClaudeCodeCliProfile,
    CodexCliProfile,
    CodingTaskRequest,
    CursorCliProfile,
    OpenCodeCliProfile,
)
from curupira.providers.claude import ClaudeCodeCliAdapter
from curupira.providers.codex import CodexCliAdapter
from curupira.providers.copilot import CopilotCliAdapter, CopilotCliProfile
from curupira.providers.cursor import CursorCliAdapter
from curupira.providers.gemini import GeminiCliAdapter, GeminiCliProfile
from curupira.providers.kilo import KiloCliAdapter, KiloCliProfile
from curupira.providers.opencode import OpenCodeCliAdapter
from curupira.providers.pi import PiCliAdapter, PiCliProfile
from curupira.providers.qwen import QwenCodeCliAdapter, QwenCodeCliProfile


def test_default_interactive_launch_returns_none(tmp_path: Path) -> None:
    class _BareAdapter(CodingAgentCliAdapter):
        executable = "bare"
        provider = "bare"
        profile_model = OpenCodeCliProfile
        display_name = "Bare"
        install_url = "https://example.test/bare"

        @override
        def build_arguments(self, request: CodingTaskRequest) -> tuple[str, ...]:
            return (request.message,)

    assert (
        _BareAdapter().interactive_launch(
            OpenCodeCliProfile(), model=None, prompt=None, cwd=tmp_path
        )
        is None
    )


def test_default_pty_env_allowlist_and_excludes_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("HOME", "/home/tester")
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("USER", "tester")
    monkeypatch.setenv("SHELL", "/bin/bash")
    # Test marker only; must not appear in the allowlisted PTY env.
    forbidden_host_value = "should-not-leak"
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", forbidden_host_value)
    monkeypatch.setenv("GITHUB_TOKEN", "also-not-forwarded")
    monkeypatch.delenv("TERM", raising=False)
    monkeypatch.delenv("COLORTERM", raising=False)

    env = default_pty_env(extra={"CUSTOM": "1"})

    assert env == {
        "PATH": "/usr/bin",
        "HOME": "/home/tester",
        "LANG": "C.UTF-8",
        "USER": "tester",
        "SHELL": "/bin/bash",
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
        "CUSTOM": "1",
    }
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "GITHUB_TOKEN" not in env
    assert os.environ["AWS_SECRET_ACCESS_KEY"] == forbidden_host_value


def test_spec_available_uses_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    executable = fake_bin / "fake-agent"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(fake_bin))

    present = InteractiveLaunchSpec(argv=("fake-agent", "--model", "x"), cwd=tmp_path)
    missing = InteractiveLaunchSpec(argv=("missing-agent",), cwd=tmp_path)

    assert spec_available(present) is True
    assert spec_available(missing) is False
    assert spec_available(InteractiveLaunchSpec(argv=(), cwd=tmp_path)) is False


def test_every_registered_adapter_interactive_launch_never_raises(tmp_path: Path) -> None:
    for provider, adapter_cls in registered().items():
        profile = adapter_cls.profile_model.model_validate({"provider": provider})
        result = adapter_cls().interactive_launch(profile, model=None, prompt=None, cwd=tmp_path)
        assert result is None or isinstance(result, InteractiveLaunchSpec), provider
        if result is not None:
            assert result.argv[0] == adapter_cls.executable
            assert result.cwd == tmp_path
            assert isinstance(result.env, dict)
            assert isinstance(result.notes, tuple)


def test_claude_interactive_launch_argv(tmp_path: Path) -> None:
    adapter = ClaudeCodeCliAdapter()
    profile = ClaudeCodeCliProfile(
        agent="reviewer",
        effort="high",
        permission_mode="plan",
        permission_prompts="none",
    )

    bare = adapter.interactive_launch(profile, model=None, prompt=None, cwd=tmp_path)
    assert bare is not None
    assert bare.argv == (
        "claude",
        "--agent",
        "reviewer",
        "--effort",
        "high",
        "--permission-mode",
        "plan",
    )
    assert "--permission-prompts" not in bare.argv
    assert "-p" not in bare.argv
    assert "stream-json" not in bare.argv

    with_model = adapter.interactive_launch(
        profile, model="sonnet", prompt="Start here", cwd=tmp_path
    )
    assert with_model is not None
    assert with_model.argv == (
        "claude",
        "--model",
        "sonnet",
        "--agent",
        "reviewer",
        "--effort",
        "high",
        "--permission-mode",
        "plan",
        "Start here",
    )


def test_codex_interactive_launch_argv(tmp_path: Path) -> None:
    adapter = CodexCliAdapter()
    profile = CodexCliProfile(
        agent="work",
        effort="high",
        sandbox="workspace-write",
        auto_review=True,
    )

    bare = adapter.interactive_launch(profile, model=None, prompt=None, cwd=tmp_path)
    assert bare is not None
    assert bare.argv == (
        "codex",
        "--profile",
        "work",
        "--config",
        f"model_reasoning_effort={json.dumps('high')}",
        "--sandbox",
        "workspace-write",
        "--config",
        'approval_policy="on-request"',
        "--config",
        'approvals_reviewer="auto_review"',
    )
    assert "exec" not in bare.argv
    assert "--json" not in bare.argv

    with_prompt = adapter.interactive_launch(
        CodexCliProfile(), model="gpt-5", prompt="Investigate", cwd=tmp_path
    )
    assert with_prompt is not None
    assert with_prompt.argv == ("codex", "--model", "gpt-5", "Investigate")


def test_opencode_interactive_launch_argv(tmp_path: Path) -> None:
    adapter = OpenCodeCliAdapter()
    profile = OpenCodeCliProfile(
        model="anthropic/claude",
        agent="build",
        effort="high",
        auto_approve=True,
    )

    bare = adapter.interactive_launch(profile, model=None, prompt=None, cwd=tmp_path)
    assert bare is not None
    assert bare.argv == ("opencode", "--agent", "build", "--variant", "high", "--auto")
    assert "run" not in bare.argv
    assert "--format" not in bare.argv

    full = adapter.interactive_launch(
        profile, model="anthropic/claude", prompt="Ship it", cwd=tmp_path
    )
    assert full is not None
    assert full.argv == (
        "opencode",
        "--model",
        "anthropic/claude",
        "--agent",
        "build",
        "--variant",
        "high",
        "--prompt",
        "Ship it",
        "--auto",
    )


def test_cursor_interactive_launch_argv_and_auto_model(tmp_path: Path) -> None:
    adapter = CursorCliAdapter()
    profile = CursorCliProfile(agent="plan", force=True, trust=True)

    bare = adapter.interactive_launch(profile, model=None, prompt=None, cwd=tmp_path)
    assert bare is not None
    assert bare.argv == ("agent", "--mode", "plan", "--force", "--trust")
    assert "--print" not in bare.argv
    assert "stream-json" not in bare.argv

    resolved = resolve_assistant_model(CursorCliAdapter, "auto")
    assert resolved.model == "auto"
    auto = adapter.interactive_launch(
        profile, model=resolved.model, prompt="Refactor auth", cwd=tmp_path
    )
    assert auto is not None
    assert auto.argv == (
        "agent",
        "--mode",
        "plan",
        "--model",
        "auto",
        "--force",
        "--trust",
        "Refactor auth",
    )


def test_gemini_interactive_launch_argv(tmp_path: Path) -> None:
    adapter = GeminiCliAdapter()
    profile = GeminiCliProfile(approval_mode="yolo", skip_trust=True)

    bare = adapter.interactive_launch(profile, model=None, prompt=None, cwd=tmp_path)
    assert bare is not None
    assert bare.argv == ("gemini", "--approval-mode", "yolo", "--skip-trust")
    assert "--output-format" not in bare.argv
    assert not any(part.startswith("--prompt=") for part in bare.argv)

    full = adapter.interactive_launch(
        profile, model="flash", prompt="Explain this repo", cwd=tmp_path
    )
    assert full is not None
    assert full.argv == (
        "gemini",
        "--model",
        "flash",
        "--approval-mode",
        "yolo",
        "--skip-trust",
        "Explain this repo",
    )


def test_copilot_interactive_launch_argv(tmp_path: Path) -> None:
    adapter = CopilotCliAdapter()
    profile = CopilotCliProfile(
        agent="reviewer",
        effort="high",
        allow_all_tools=True,
        allow_tools=("shell",),
        deny_tools=("web",),
    )

    bare = adapter.interactive_launch(profile, model=None, prompt=None, cwd=tmp_path)
    assert bare is not None
    assert bare.argv == (
        "copilot",
        "--agent=reviewer",
        "--reasoning-effort=high",
        "--allow-all-tools",
        "--allow-tool=shell",
        "--deny-tool=web",
    )
    assert "--output-format=json" not in bare.argv
    assert "--no-ask-user" not in bare.argv
    assert not any(part.startswith("--session-id=") for part in bare.argv)
    assert not any(part.startswith("--prompt=") for part in bare.argv)

    full = adapter.interactive_launch(
        CopilotCliProfile(), model="gpt-5", prompt="Fix CI", cwd=tmp_path
    )
    assert full is not None
    assert full.argv == ("copilot", "--model=gpt-5", "--interactive=Fix CI")


def test_kilo_interactive_launch_argv(tmp_path: Path) -> None:
    adapter = KiloCliAdapter()
    profile = KiloCliProfile(agent="coder", effort="high", auto_approve=True)

    bare = adapter.interactive_launch(profile, model=None, prompt=None, cwd=tmp_path)
    assert bare is not None
    assert bare.argv == ("kilo", "--agent", "coder", "--variant", "high", "--auto")
    assert "run" not in bare.argv
    assert "--format" not in bare.argv

    full = adapter.interactive_launch(
        profile, model="anthropic/claude", prompt="Continue", cwd=tmp_path
    )
    assert full is not None
    assert full.argv == (
        "kilo",
        "--model",
        "anthropic/claude",
        "--agent",
        "coder",
        "--variant",
        "high",
        "--prompt",
        "Continue",
        "--auto",
    )


def test_pi_interactive_launch_argv(tmp_path: Path) -> None:
    adapter = PiCliAdapter()
    profile = PiCliProfile(
        model="sonnet",
        model_provider="openai",
        effort="high",
        tools=("read", "bash"),
        exclude_tools=("write",),
        approve=True,
    )

    bare = adapter.interactive_launch(profile, model=None, prompt=None, cwd=tmp_path)
    assert bare is not None
    assert bare.argv == (
        "pi",
        "--provider",
        "openai",
        "--thinking",
        "high",
        "--tools",
        "read,bash",
        "--exclude-tools",
        "write",
        "--approve",
    )
    assert "--mode" not in bare.argv
    assert "json" not in bare.argv

    full = adapter.interactive_launch(
        PiCliProfile(approve=False), model="sonnet", prompt="Review", cwd=tmp_path
    )
    assert full is not None
    assert full.argv == ("pi", "--model", "sonnet", "--no-approve", "--", "Review")


def test_qwen_interactive_launch_argv(tmp_path: Path) -> None:
    adapter = QwenCodeCliAdapter()
    profile = QwenCodeCliProfile(approval_mode="yolo", max_session_turns=12)

    bare = adapter.interactive_launch(profile, model=None, prompt=None, cwd=tmp_path)
    assert bare is not None
    assert bare.argv == (
        "qwen",
        "--approval-mode",
        "yolo",
        "--max-session-turns",
        "12",
    )
    assert "--output-format" not in bare.argv
    assert not any(part.startswith("--prompt=") for part in bare.argv)

    full = adapter.interactive_launch(
        profile, model="qwen-coder-plus", prompt="Bootstrap", cwd=tmp_path
    )
    assert full is not None
    assert full.argv == (
        "qwen",
        "--model",
        "qwen-coder-plus",
        "--approval-mode",
        "yolo",
        "--max-session-turns",
        "12",
        "--prompt-interactive",
        "Bootstrap",
    )
