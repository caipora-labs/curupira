"""Smoke checks for the thin Python distribution layer."""

from __future__ import annotations

import tomllib
from pathlib import Path

import curupira


def test_version_export() -> None:
    assert curupira.__version__ == "0.2.0"
    assert curupira.__all__ == ["__version__"]


def test_cli_wheel_has_no_hard_python_deps() -> None:
    """The maturin wheel ships the Rust binary; SDK and triggers are optional extras."""
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data["project"]
    assert project["dependencies"] == []
    extras = project["optional-dependencies"]
    assert set(extras) == {"github", "azure", "trello", "monday", "extensions"}
    assert extras["github"] == ["curupira-github==0.2.0"]
    assert extras["azure"] == ["curupira-azure==0.2.0"]
    assert extras["trello"] == ["curupira-trello==0.2.0"]
    assert extras["monday"] == ["curupira-monday==0.2.0"]
    assert set(extras["extensions"]) == {
        "curupira-github==0.2.0",
        "curupira-azure==0.2.0",
        "curupira-trello==0.2.0",
        "curupira-monday==0.2.0",
    }
    assert "curupira-sdk" not in " ".join(
        dep for group in extras.values() for dep in group
    )
