"""Packaged README / metadata must not ship retired OpsCli branding."""

from __future__ import annotations

import importlib.util
import io
import tarfile
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_packaged_readme.py"


def _load_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_packaged_readme", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_wheel(dist: Path, *, description: str) -> None:
    metadata = (
        "Metadata-Version: 2.1\n"
        "Name: curupira\n"
        "Version: 0.1.0\n"
        "Summary: test\n"
        "Description-Content-Type: text/markdown\n"
        "\n"
        f"{description}\n"
    )
    wheel = dist / "curupira-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("curupira-0.1.0.dist-info/METADATA", metadata)


def _write_sdist(dist: Path, *, description: str, include_readme: bool = True) -> None:
    metadata = (
        "Metadata-Version: 2.1\n"
        "Name: curupira\n"
        "Version: 0.1.0\n"
        "Summary: test\n"
        "Description-Content-Type: text/markdown\n"
        "\n"
        f"{description}\n"
    ).encode()
    archive_path = dist / "curupira-0.1.0.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        pkg = tarfile.TarInfo(name="curupira-0.1.0/PKG-INFO")
        pkg.size = len(metadata)
        archive.addfile(pkg, io.BytesIO(metadata))
        if include_readme:
            readme = description.encode()
            member = tarfile.TarInfo(name="curupira-0.1.0/README.md")
            member.size = len(readme)
            archive.addfile(member, io.BytesIO(readme))


def _write_pair(dist: Path, *, description: str) -> None:
    dist.mkdir(parents=True, exist_ok=True)
    _write_wheel(dist, description=description)
    _write_sdist(dist, description=description)


def test_clean_description_passes(tmp_path: Path) -> None:
    checker = _load_checker()
    _write_pair(tmp_path, description="# Curupira\n\nDispatch tasks locally.\n")

    checker.assert_no_opscli_in_distributions(tmp_path)


def test_opscli_in_metadata_description_fails(tmp_path: Path) -> None:
    checker = _load_checker()
    _write_pair(tmp_path, description="# OpsCli\n\nLegacy name.\n")

    with pytest.raises(SystemExit, match=r"(?i)opscli"):
        checker.assert_no_opscli_in_distributions(tmp_path)


def test_opscli_case_insensitive_in_sdist_readme_fails(tmp_path: Path) -> None:
    checker = _load_checker()
    dist = tmp_path
    dist.mkdir(parents=True, exist_ok=True)
    _write_wheel(dist, description="# Curupira\n")
    _write_sdist(dist, description="# Welcome to OPSCLI\n")

    with pytest.raises(SystemExit, match=r"(?i)opscli"):
        checker.assert_no_opscli_in_distributions(tmp_path)


def test_opscli_only_in_wheel_readme_member_fails(tmp_path: Path) -> None:
    checker = _load_checker()
    dist = tmp_path
    dist.mkdir(parents=True, exist_ok=True)
    metadata = (
        "Metadata-Version: 2.1\n"
        "Name: curupira\n"
        "Version: 0.1.0\n"
        "Summary: test\n"
        "Description-Content-Type: text/markdown\n"
        "\n"
        "# Curupira\n"
    )
    wheel = dist / "curupira-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("curupira-0.1.0.dist-info/METADATA", metadata)
        archive.writestr("README.md", "This package was called OpsCli.\n")
    _write_sdist(dist, description="# Curupira\n")

    with pytest.raises(SystemExit, match=r"(?i)opscli"):
        checker.assert_no_opscli_in_distributions(tmp_path)


def test_failure_reports_archive_member_line_and_snippet(tmp_path: Path) -> None:
    checker = _load_checker()
    dist = tmp_path
    dist.mkdir(parents=True, exist_ok=True)
    metadata = (
        "Metadata-Version: 2.1\n"
        "Name: curupira\n"
        "Version: 0.1.0\n"
        "Summary: test\n"
        "Description-Content-Type: text/markdown\n"
        "\n"
        "# Curupira\n"
    )
    wheel = dist / "curupira-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("curupira-0.1.0.dist-info/METADATA", metadata)
        archive.writestr("README.md", "Curupira\n\nFormerly OpsCli branding.\n")
    _write_sdist(dist, description="# Curupira\n")

    with pytest.raises(SystemExit) as excinfo:
        checker.assert_no_opscli_in_distributions(tmp_path)

    message = str(excinfo.value)
    assert "curupira-0.1.0-py3-none-any.whl:README.md:3:" in message
    assert "Formerly OpsCli branding." in message


def test_missing_wheel_fails(tmp_path: Path) -> None:
    checker = _load_checker()
    _write_sdist(tmp_path, description="# Curupira\n")

    with pytest.raises(SystemExit, match="wheel"):
        checker.assert_no_opscli_in_distributions(tmp_path)


def test_cli_no_build_no_twine_on_clean_dist(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    checker = _load_checker()
    _write_pair(tmp_path, description="# Curupira\n")

    checker.main(["--dist", str(tmp_path), "--no-build", "--no-twine"])

    assert "opscli" in capsys.readouterr().out
