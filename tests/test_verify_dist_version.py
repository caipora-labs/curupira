"""Tag and distribution version contract for the TestPyPI rehearsal."""

from __future__ import annotations

import importlib.util
import io
import re
import tarfile
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_dist_version.py"


def _load_verifier() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_dist_version", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_wheel(dist: Path, version: str) -> None:
    metadata = f"Metadata-Version: 2.1\nName: curupira\nVersion: {version}\n"
    wheel = dist / f"curupira-{version}-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr(f"curupira-{version}.dist-info/METADATA", metadata)


def _write_sdist(dist: Path, version: str) -> None:
    payload = f"Metadata-Version: 2.1\nName: curupira\nVersion: {version}\n".encode()
    member = tarfile.TarInfo(name=f"curupira-{version}/PKG-INFO")
    member.size = len(payload)
    archive_path = dist / f"curupira-{version}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.addfile(member, io.BytesIO(payload))


def _write_pair(dist: Path, version: str) -> None:
    dist.mkdir(parents=True, exist_ok=True)
    _write_wheel(dist, version)
    _write_sdist(dist, version)


def test_dev_tag_matches_wheel_and_sdist(tmp_path: Path) -> None:
    verifier = _load_verifier()
    _write_pair(tmp_path, "0.1.0.dev0")

    assert verifier.verify_distribution_version(tmp_path, "v0.1.0.dev0", require_dev=True) == (
        "0.1.0.dev0"
    )


def test_cli_prints_the_dev_version(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    verifier = _load_verifier()
    _write_pair(tmp_path, "0.1.0.dev0")

    verifier.main(["--dist", str(tmp_path), "--tag", "v0.1.0.dev0", "--require-dev"])

    assert capsys.readouterr().out == "0.1.0.dev0\n"


def test_stable_tag_matches_without_the_dev_requirement(tmp_path: Path) -> None:
    verifier = _load_verifier()
    _write_pair(tmp_path, "0.1.0")

    assert verifier.verify_distribution_version(tmp_path, "v0.1.0") == "0.1.0"


def test_dev_tag_rejects_a_stable_artifact(tmp_path: Path) -> None:
    verifier = _load_verifier()
    _write_pair(tmp_path, "0.1.0")

    with pytest.raises(SystemExit, match="does not match"):
        verifier.verify_distribution_version(tmp_path, "v0.1.0.dev0", require_dev=True)


def test_dev_requirement_rejects_a_stable_tag(tmp_path: Path) -> None:
    verifier = _load_verifier()
    _write_pair(tmp_path, "0.1.0")

    with pytest.raises(SystemExit, match="development tag"):
        verifier.verify_distribution_version(tmp_path, "v0.1.0", require_dev=True)


def test_dev_requirement_rejects_a_hyphenated_tag(tmp_path: Path) -> None:
    verifier = _load_verifier()
    _write_pair(tmp_path, "0.1.0.dev0")

    with pytest.raises(SystemExit, match="development tag"):
        verifier.verify_distribution_version(tmp_path, "v0.1.0-dev0", require_dev=True)


def test_mismatched_wheel_and_sdist_fail(tmp_path: Path) -> None:
    verifier = _load_verifier()
    tmp_path.mkdir(parents=True, exist_ok=True)
    _write_wheel(tmp_path, "0.1.0.dev0")
    _write_sdist(tmp_path, "0.1.0.dev1")

    with pytest.raises(SystemExit, match="do not share one version"):
        verifier.verify_distribution_version(tmp_path, "v0.1.0.dev0", require_dev=True)


def test_wheels_only_artifact_is_allowed(tmp_path: Path) -> None:
    verifier = _load_verifier()
    tmp_path.mkdir(parents=True, exist_ok=True)
    _write_wheel(tmp_path, "0.1.0")

    assert verifier.verify_distribution_version(tmp_path, require_sdist=False) == "0.1.0"
    with pytest.raises(SystemExit, match="sdist"):
        verifier.verify_distribution_version(tmp_path, require_sdist=True)


def test_cli_allow_wheels_only(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    verifier = _load_verifier()
    tmp_path.mkdir(parents=True, exist_ok=True)
    _write_wheel(tmp_path, "0.1.0")

    verifier.main(["--dist", str(tmp_path), "--allow-wheels-only"])

    assert capsys.readouterr().out == "0.1.0\n"


def test_multiple_matching_wheels_share_one_version(tmp_path: Path) -> None:
    verifier = _load_verifier()
    _write_pair(tmp_path, "0.1.0")
    metadata = "Metadata-Version: 2.1\nName: curupira\nVersion: 0.1.0\n"
    second = tmp_path / "curupira-0.1.0-cp311-abi3-win_amd64.whl"
    with zipfile.ZipFile(second, "w") as archive:
        archive.writestr("curupira-0.1.0.dist-info/METADATA", metadata)

    assert verifier.verify_distribution_version(tmp_path, "v0.1.0") == "0.1.0"


def test_declared_version_is_canonical_release_or_dev() -> None:
    from curupira import __version__

    assert re.fullmatch(r"\d+\.\d+\.\d+(\.dev\d+)?", __version__)
