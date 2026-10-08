"""Required GitHub check-run names for publish gates."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "require_ci_checks.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("require_ci_checks", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_required_checks_cover_platforms_and_package_gate() -> None:
    module = _load_module()
    required = module.REQUIRED_CHECKS
    assert "Build and smoke-test distributions" in required
    assert "Tests (Linux x86_64, Python 3.11)" in required
    assert "Tests (Linux aarch64, Python 3.13)" in required
    assert "Tests (macOS arm64, Python 3.13)" in required
    assert "Tests (macOS x86_64, Python 3.13)" in required
    assert "Tests (Windows amd64, Python 3.13)" in required
