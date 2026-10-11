"""Tests for surgical ``[assistant]`` TOML persistence."""

from __future__ import annotations

import stat
import tomllib
from pathlib import Path

import pytest

from curupira.tui.assistant_persist import (
    UnsupportedAssistantTomlError,
    persist_assistant_agent,
)


def test_persist_appends_assistant_table(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    config.write_text("[settings]\nmax_active_tasks = 1\n", encoding="utf-8")
    before = tomllib.loads(config.read_text(encoding="utf-8"))
    persist_assistant_agent(config, agent="cursor")
    after = tomllib.loads(config.read_text(encoding="utf-8"))
    assert {key: value for key, value in after.items() if key != "assistant"} == before
    assert after["assistant"] == {"agent": "cursor"}


def test_persist_updates_existing_assistant_agent_and_clears_model(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    config.write_text(
        '[agents.defaults]\nprofile = "x"\n\n[assistant]\nagent = "claude"\nmodel = "auto"\n',
        encoding="utf-8",
    )
    before = tomllib.loads(config.read_text(encoding="utf-8"))
    before_without = {key: value for key, value in before.items() if key != "assistant"}
    persist_assistant_agent(config, agent="opencode", model=None)
    after = tomllib.loads(config.read_text(encoding="utf-8"))
    after_without = {key: value for key, value in after.items() if key != "assistant"}
    assert after_without == before_without
    assert after["assistant"] == {"agent": "opencode"}


def test_persist_writes_model_when_provided(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    config.write_text('[assistant]\nagent = "cursor"\n', encoding="utf-8")
    persist_assistant_agent(config, agent="cursor", model="auto")
    after = tomllib.loads(config.read_text(encoding="utf-8"))
    assert after["assistant"] == {"agent": "cursor", "model": "auto"}


def test_persist_requires_existing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="configuration file not found"):
        persist_assistant_agent(tmp_path / "missing.toml", agent="cursor")


def test_persist_preserves_other_tables_and_eol_comments(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    config.write_text(
        "\n".join(
            [
                "[settings]",
                "max_active_tasks = 2",
                "",
                "[agents.defaults]",
                'profile = "opencode"',
                "",
                "[agents.profiles.opencode]",
                'provider = "opencode"',
                'agent = "issue-resolver"',
                'model = "provider/model"',
                "",
                "[assistant]",
                'agent = "claude"  # keep-me',
                'model = "sonnet"  # model-note',
                "",
            ]
        ),
        encoding="utf-8",
    )
    before = tomllib.loads(config.read_text(encoding="utf-8"))
    before_without = {key: value for key, value in before.items() if key != "assistant"}
    persist_assistant_agent(config, agent="cursor", model="auto")
    text = config.read_text(encoding="utf-8")
    after = tomllib.loads(text)
    after_without = {key: value for key, value in after.items() if key != "assistant"}
    assert after_without == before_without
    assert after["assistant"] == {"agent": "cursor", "model": "auto"}
    assert 'agent = "cursor"  # keep-me' in text
    assert 'model = "auto"  # model-note' in text


def test_persist_refuses_inline_table_without_writing(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    original = 'assistant = {model = "x"}\n[settings]\nmax_active_tasks = 1\n'
    config.write_text(original, encoding="utf-8")
    with pytest.raises(UnsupportedAssistantTomlError, match="unsupported TOML shape"):
        persist_assistant_agent(config, agent="cursor")
    assert config.read_text(encoding="utf-8") == original


def test_persist_refuses_dotted_key_without_writing(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    original = 'assistant.agent = "codex"\n[settings]\nmax_active_tasks = 1\n'
    config.write_text(original, encoding="utf-8")
    with pytest.raises(UnsupportedAssistantTomlError, match="unsupported TOML shape"):
        persist_assistant_agent(config, agent="cursor")
    assert config.read_text(encoding="utf-8") == original


def test_persist_refuses_quoted_header_without_writing(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    original = '["assistant"]\nagent = "claude"\n[settings]\nmax_active_tasks = 1\n'
    config.write_text(original, encoding="utf-8")
    with pytest.raises(UnsupportedAssistantTomlError, match="unsupported TOML shape"):
        persist_assistant_agent(config, agent="cursor")
    assert config.read_text(encoding="utf-8") == original


def test_persist_atomic_write_preserves_file_mode(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    config.write_text("[settings]\nmax_active_tasks = 1\n", encoding="utf-8")
    config.chmod(0o640)
    persist_assistant_agent(config, agent="cursor")
    assert stat.S_IMODE(config.stat().st_mode) == 0o640
    assert tomllib.loads(config.read_text(encoding="utf-8"))["assistant"]["agent"] == "cursor"


def test_persist_preserves_crlf_newline_style(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    config.write_bytes(
        b"[settings]\r\n"
        b"max_active_tasks = 1\r\n"
        b"\r\n"
        b"[assistant]\r\n"
        b'agent = "claude"\r\n'
        b'model = "auto"\r\n'
    )
    persist_assistant_agent(config, agent="cursor", model=None)
    raw = config.read_bytes()
    assert b"\r\n" in raw
    assert b"\n" not in raw.replace(b"\r\n", b"")
    after = tomllib.loads(raw.decode("utf-8"))
    assert after["assistant"] == {"agent": "cursor"}
    assert after["settings"] == {"max_active_tasks": 1}


def test_persist_removing_model_does_not_leave_extra_blank_line(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    config.write_text(
        '[assistant]\nagent = "claude"\nmodel = "auto"\n',
        encoding="utf-8",
    )
    persist_assistant_agent(config, agent="opencode", model=None)
    assert config.read_text(encoding="utf-8") == '[assistant]\nagent = "opencode"\n'
