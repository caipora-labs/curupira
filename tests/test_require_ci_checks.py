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


def test_required_checks_cover_ubuntu_python_matrix_and_package() -> None:
    module = _load_module()
    required = module.REQUIRED_CHECKS
    assert required == {
        "Ruff lint and format",
        "Strict type check",
        "Tests (Python 3.11)",
        "Tests (Python 3.12)",
        "Tests (Python 3.13)",
        "Tests (Python 3.14)",
        "Build and smoke-test distributions",
    }
