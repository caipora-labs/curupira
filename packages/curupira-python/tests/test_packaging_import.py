"""Smoke checks for the thin Python distribution layer."""

from __future__ import annotations

import curupira


def test_version_export() -> None:
    assert curupira.__version__ == "0.2.0"
    assert curupira.__all__ == ["__version__"]
