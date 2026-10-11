"""Tests for surgical ``[assistant]`` TOML persistence."""

from pathlib import Path

import pytest

from curupira.tui.assistant_persist import persist_assistant_agent


def test_persist_appends_assistant_table(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    config.write_text("[settings]\nmax_active_tasks = 1\n", encoding="utf-8")
    persist_assistant_agent(config, agent="cursor")
    text = config.read_text(encoding="utf-8")
    assert "[assistant]" in text
    assert 'agent = "cursor"' in text
    assert "model" not in text.split("[assistant]", 1)[1]


def test_persist_updates_existing_assistant_agent_and_clears_model(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    config.write_text(
        '[agents.defaults]\nprofile = "x"\n\n[assistant]\nagent = "claude"\nmodel = "auto"\n',
        encoding="utf-8",
    )
    persist_assistant_agent(config, agent="opencode", model=None)
    text = config.read_text(encoding="utf-8")
    assert 'agent = "opencode"' in text
    assert "model" not in text.split("[assistant]", 1)[1]
    assert "[agents.defaults]" in text


def test_persist_writes_model_when_provided(tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    config.write_text('[assistant]\nagent = "cursor"\n', encoding="utf-8")
    persist_assistant_agent(config, agent="cursor", model="auto")
    text = config.read_text(encoding="utf-8")
    assert 'agent = "cursor"' in text
    assert 'model = "auto"' in text


def test_persist_requires_existing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="configuration file not found"):
        persist_assistant_agent(tmp_path / "missing.toml", agent="cursor")
