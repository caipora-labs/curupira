"""Check that the built distributions of one package carry the release version."""

from __future__ import annotations

import argparse
import shutil
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path

from packaging.utils import canonicalize_name, parse_sdist_filename, parse_wheel_filename
from packaging.version import Version


def verify_distribution_version(dist: Path, project: str, version: str) -> list[Path]:
    """Return the wheel and sdist of ``project`` in ``dist`` after checking their version.

    Other packages in ``dist`` are ignored: each package is released on its own version.
    Versions compare as PEP 440, so ``0.1.0dev0`` matches the built ``0.1.0.dev0``.
    """
    expected = Version(version)
    paths = _project_distributions(dist, project)
    wheels = [path for path in paths if path.suffix == ".whl"]
    sdists = [path for path in paths if path.name.endswith(".tar.gz")]
    if not wheels or not sdists:
        found = [path.name for path in paths]
        message = f"Expected a wheel and an sdist for {project} in {dist}, found {found}"
        raise SystemExit(message)
    for path in paths:
        built = Version(_metadata_version(path))
        if built != expected:
            message = f"{path.name} is version {built}, expected {expected}"
            raise SystemExit(message)
    return paths


def _project_distributions(dist: Path, project: str) -> list[Path]:
    name = canonicalize_name(project)
    matches: list[Path] = []
    for path in sorted([*dist.glob("*.whl"), *dist.glob("*.tar.gz")]):
        if path.suffix == ".whl":
            distribution, *_ = parse_wheel_filename(path.name)
        else:
            distribution, _ = parse_sdist_filename(path.name)
        if distribution == name:
            matches.append(path)
    return matches


def _metadata_version(path: Path) -> str:
    if path.suffix == ".whl":
        return _wheel_version(path)
    return _sdist_version(path)


def _wheel_version(wheel: Path) -> str:
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(
            (name for name in archive.namelist() if name.endswith(".dist-info/METADATA")),
            None,
        )
        if metadata_name is None:
            message = f"Missing METADATA in {wheel}"
            raise SystemExit(message)
        metadata = Parser().parsestr(archive.read(metadata_name).decode())
    return _require_version(metadata["Version"], wheel)


def _sdist_version(source: Path) -> str:
    with tarfile.open(source, "r:gz") as archive:
        metadata_file = next(
            (member for member in archive.getmembers() if member.name.endswith("/PKG-INFO")),
            None,
        )
        if metadata_file is None:
            message = f"Missing PKG-INFO in {source}"
            raise SystemExit(message)
        extracted = archive.extractfile(metadata_file)
        if extracted is None:
            message = f"Cannot read metadata from {source}"
            raise SystemExit(message)
        metadata = Parser().parsestr(extracted.read().decode())
    return _require_version(metadata["Version"], source)


def _require_version(version: str | None, path: Path) -> str:
    if not version:
        message = f"Missing Version in {path}"
        raise SystemExit(message)
    return version


def main(argv: list[str] | None = None) -> None:
    """Verify the project's distributions and optionally copy them for upload."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--project", required=True, help="Distribution name, e.g. curupira-sdk")
    parser.add_argument("--version", required=True, help="Release version from the tag")
    parser.add_argument(
        "--copy-to",
        type=Path,
        help="Copy the verified wheel and sdist into this directory",
    )
    args = parser.parse_args(argv)
    paths = verify_distribution_version(args.dist, args.project, args.version)
    if args.copy_to is not None:
        args.copy_to.mkdir(parents=True, exist_ok=True)
        for path in paths:
            shutil.copy2(path, args.copy_to / path.name)
    print(f"verified {len(paths)} distributions for {args.project} {args.version}")


if __name__ == "__main__":
    main()
