"""Official extensions print manifests without side effects."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / "python"


@pytest.mark.parametrize(
    "module",
    [
        "curupira_official.github_ext",
        "curupira_official.azure_ext",
        "curupira_official.trello_ext",
        "curupira_official.monday_ext",
    ],
)
def test_print_manifest(module: str) -> None:
    env = {**os.environ, "PYTHONPATH": str(PYTHON)}
    proc = subprocess.run(
        [sys.executable, "-m", module, "--curupira-print-manifest"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
    )
    assert "manifest_version = 1" in proc.stdout
    assert "protocol_version = 1" in proc.stdout
