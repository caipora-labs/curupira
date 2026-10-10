"""Coding-agent registry contract and built-in registration."""

import pytest
from pydantic import ValidationError

import curupira.agents.registry as agent_registry
from curupira.agents.claude import ClaudeCodeCliAdapter
from curupira.agents.codex import CodexCliAdapter
from curupira.agents.copilot import CopilotCliAdapter
from curupira.agents.cursor import CursorCliAdapter
from curupira.agents.gemini import GeminiCliAdapter
from curupira.agents.opencode import OpenCodeCliAdapter
from curupira.agents.pi import PiCliAdapter
from curupira.models import CodingTaskRequest, CursorCliProfile
from curupira.models.profiles import parse_cli_profile
from tests.plugins.echo_agent_plugin import EchoCliAdapter, MismatchedCliAdapter


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    agent_registry.registered()
    monkeypatch.setattr(agent_registry, "_ADAPTERS", dict(agent_registry._ADAPTERS))


def test_built_in_providers_are_registered() -> None:
    adapters = agent_registry.registered()

    assert adapters == {
        "claude": ClaudeCodeCliAdapter,
        "codex": CodexCliAdapter,
        "copilot": CopilotCliAdapter,
        "cursor": CursorCliAdapter,
        "gemini": GeminiCliAdapter,
        "opencode": OpenCodeCliAdapter,
        "pi": PiCliAdapter,
    }
    assert {provider: adapter.display_name for provider, adapter in adapters.items()} == {
        "claude": "Claude Code",
        "codex": "Codex",
        "copilot": "GitHub Copilot CLI",
        "cursor": "Cursor",
        "gemini": "Gemini CLI",
        "opencode": "OpenCode",
        "pi": "pi",
    }
    assert all(adapter.install_url.startswith("https://") for adapter in adapters.values())


def test_register_rejects_duplicate_provider() -> None:
    with pytest.raises(ValueError, match="coding agent provider already registered: cursor"):
        agent_registry.register(CursorCliAdapter)


def test_register_rejects_mismatched_profile_default() -> None:
    with pytest.raises(ValueError, match="must default provider to 'mismatch', not 'echo'"):
        agent_registry.register(MismatchedCliAdapter)

    assert "mismatch" not in agent_registry.registered()


def test_register_rejects_profile_model_outside_cli_profiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UntypedCliAdapter(EchoCliAdapter):
        provider = "untyped"

    monkeypatch.setattr(UntypedCliAdapter, "profile_model", CodingTaskRequest)

    with pytest.raises(ValueError, match="must declare a profile_model that extends"):
        agent_registry.register(UntypedCliAdapter)


def test_register_then_get_returns_adapter_class() -> None:
    agent_registry.register(EchoCliAdapter)

    assert agent_registry.get("echo") is EchoCliAdapter
    assert list(agent_registry.registered())[-1] == "echo"


def test_get_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="unknown coding agent provider: trello"):
        agent_registry.get("trello")


@pytest.mark.parametrize(
    ("value", "detail"),
    [
        ({}, "provider is required"),
        ({"provider": 7}, "provider must be a string"),
    ],
)
def test_profile_requires_a_string_provider(value: dict[str, object], detail: str) -> None:
    with pytest.raises(ValueError, match=detail):
        parse_cli_profile(value)


def test_profile_instances_pass_through_unchanged() -> None:
    profile = CursorCliProfile(agent="ask")

    assert parse_cli_profile(profile) is profile
    assert CodingTaskRequest.model_validate(
        {"cwd": ".", "message": "Fix", "profile": {"provider": "cursor", "agent": "ask"}}
    ).profile == CursorCliProfile(agent="ask")
    with pytest.raises(ValidationError, match="provider is required"):
        CodingTaskRequest.model_validate({"cwd": ".", "message": "Fix", "profile": {}})
