"""Compile ``curupi._native`` into Hatchling wheels with maturin."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    """Package the PyO3 extension for standard wheels and skip editable installs."""

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Compile ``curupi-core`` unless this is an editable install."""
        if version == "editable":
            return

        artifact_dir = Path(tempfile.mkdtemp(prefix="curupi-native-"))
        self._artifact_dir = artifact_dir
        wheel_tag, artifacts = _compile_native_extension(Path(self.root), artifact_dir)
        build_data["pure_python"] = False
        build_data["tag"] = wheel_tag
        force_include = build_data.setdefault("force_include", {})
        force_include.update(artifacts)

    def finalize(self, version: str, build_data: dict[str, Any], artifact_path: str) -> None:
        """Remove the temporary maturin output after Hatchling has packed the wheel."""
        del version, build_data, artifact_path
        artifact_dir = getattr(self, "_artifact_dir", None)
        if isinstance(artifact_dir, Path):
            shutil.rmtree(artifact_dir, ignore_errors=True)


def _compile_native_extension(root: Path, artifact_dir: Path) -> tuple[str, dict[str, str]]:
    wheel_dir = artifact_dir / "wheel"
    wheel_dir.mkdir()
    # Run from the repository root so maturin reads [tool.maturin] in pyproject.toml.
    # --manifest-path would make it look for that file next to the crate instead.
    command = [
        sys.executable,
        "-m",
        "maturin",
        "build",
        "--release",
        "--locked",
        "--interpreter",
        sys.executable,
        "--out",
        str(wheel_dir),
    ]
    subprocess.run(command, cwd=root, check=True)  # noqa: S603
    wheels = sorted(wheel_dir.glob("*.whl"))
    if len(wheels) != 1:
        found = [path.name for path in wheels]
        message = f"Expected one maturin wheel in {wheel_dir}, found {found}"
        raise RuntimeError(message)
    wheel = wheels[0]
    return _wheel_tag(wheel.name), _extract_native_files(wheel, artifact_dir / "artifacts")


def _wheel_tag(wheel_name: str) -> str:
    from packaging.utils import parse_wheel_filename

    _distribution, version, _build, _tags = parse_wheel_filename(wheel_name)
    marker = f"-{version}-"
    stem = wheel_name.removesuffix(".whl")
    index = stem.find(marker)
    if index == -1:
        message = f"Cannot find version {version} in wheel name {wheel_name}"
        raise RuntimeError(message)
    return stem[index + len(marker) :]


def _extract_native_files(wheel: Path, destination: Path) -> dict[str, str]:
    included: dict[str, str] = {}
    destination.mkdir()
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            name = info.filename
            if info.is_dir() or not _is_native_artifact(name):
                continue
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink)
            included[str(target)] = name
    if not included:
        message = f"Maturin wheel {wheel.name} did not contain curupi._native"
        raise RuntimeError(message)
    return included


def _is_native_artifact(name: str) -> bool:
    return name.startswith(("curupi/_native", "curupi.libs/", "curupi/.libs/"))
