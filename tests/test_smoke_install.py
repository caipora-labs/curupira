"""Platform wheel selection used by the install smoke script."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from packaging.tags import Tag

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "smoke_install.py"


def _load_smoke() -> ModuleType:
    spec = importlib.util.spec_from_file_location("smoke_install", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_select_wheel_prefers_a_compatible_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    smoke = _load_smoke()
    compatible = tmp_path / "curupira-0.1.0-cp311-abi3-linux_x86_64.whl"
    other = tmp_path / "curupira-0.1.0-cp311-abi3-win_amd64.whl"
    compatible.write_bytes(b"wheel")
    other.write_bytes(b"wheel")
    monkeypatch.setattr(
        "packaging.tags.sys_tags",
        lambda: [Tag("cp311", "abi3", "linux_x86_64")],
    )

    assert smoke.select_wheel(tmp_path) == compatible


def test_select_wheel_fails_when_no_platform_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    smoke = _load_smoke()
    wheel = tmp_path / "curupira-0.1.0-cp311-abi3-win_amd64.whl"
    wheel.write_bytes(b"wheel")
    monkeypatch.setattr("packaging.tags.sys_tags", list)

    with pytest.raises(SystemExit, match="No wheel"):
        smoke.select_wheel(tmp_path)


def test_select_wheel_fails_when_dist_is_empty(tmp_path: Path) -> None:
    smoke = _load_smoke()

    with pytest.raises(SystemExit, match="No wheels found"):
        smoke.select_wheel(tmp_path)
