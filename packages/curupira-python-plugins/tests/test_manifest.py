"""The official plugins package prints its manifest without side effects."""

from __future__ import annotations

import subprocess
import sys
from importlib.metadata import entry_points


def test_print_manifest() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "curupira_plugins", "--curupira-print-manifest"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "manifest_version = 1" in proc.stdout
    assert 'name = "curupira-plugins"' in proc.stdout
    assert "github-issues" in proc.stdout
    assert "protocol_version = 1" in proc.stdout
    assert 'type = "uvx"' in proc.stdout
    assert 'executable = "curupira-plugins"' in proc.stdout


def test_console_script_entry_point() -> None:
    scripts = entry_points(group="console_scripts")
    match = next((ep for ep in scripts if ep.name == "curupira-plugins"), None)
    assert match is not None
    assert match.value == "curupira_plugins.__main__:main"
