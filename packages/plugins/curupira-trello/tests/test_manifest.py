"""The official trello trigger prints its manifest without side effects."""

from __future__ import annotations

import subprocess
import sys


def test_print_manifest() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "curupira_trello", "--curupira-print-manifest"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "manifest_version = 1" in proc.stdout
    assert "protocol_version = 1" in proc.stdout
