"""Check that built wheels and sdists share the tag's PEP 440 version."""

from __future__ import annotations

import argparse
import re
import tarfile
import zipfile
from email.parser import Parser
from pathlib import Path

DEV_TAG = re.compile(r"v\d+\.\d+\.\d+\.dev\d+")


def verify_distribution_version(
    dist: Path,
    tag: str | None = None,
    *,
    require_dev: bool = False,
    require_sdist: bool = True,
) -> str:
    """Return the shared dist version, optionally matching a Git tag.

    A development rehearsal tag must be the canonical ``vX.Y.Z.devN`` form. The
    package version is that tag without the leading ``v``.
    """
    versions = _distribution_versions(dist, require_sdist=require_sdist)
    if len(set(versions)) != 1:
        message = f"Distributions do not share one version: {versions}"
        raise SystemExit(message)
    version = versions[0]
    if tag is None:
        if require_dev:
            message = "A development rehearsal tag is required"
            raise SystemExit(message)
        return version

    if require_dev and DEV_TAG.fullmatch(tag) is None:
        message = f"Expected a PEP 440 development tag vX.Y.Z.devN, got {tag!r}"
        raise SystemExit(message)
    expected = tag.removeprefix("v")
    if version != expected:
        message = f"Tag version {expected!r} does not match distributions: {versions}"
        raise SystemExit(message)
    return version


def _distribution_versions(dist: Path, *, require_sdist: bool = True) -> list[str]:
    wheels = sorted(dist.glob("*.whl"))
    sources = sorted(dist.glob("*.tar.gz"))
    if not wheels:
        message = f"Expected at least one wheel in {dist}"
        raise SystemExit(message)
    if not sources:
        if require_sdist:
            message = f"Expected at least one sdist in {dist}"
            raise SystemExit(message)
        return [_wheel_version(wheel) for wheel in wheels]
    wheel_versions = [_wheel_version(wheel) for wheel in wheels]
    source_versions = [_sdist_version(source) for source in sources]
    return wheel_versions + source_versions


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
    """Print the verified distribution version."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--tag", default="")
    parser.add_argument(
        "--require-dev",
        action="store_true",
        help="Require tag vX.Y.Z.devN and an equal distribution version",
    )
    parser.add_argument(
        "--allow-wheels-only",
        action="store_true",
        help="Allow a platform artifact directory that contains wheels but no sdist",
    )
    args = parser.parse_args(argv)
    tag = args.tag or None
    print(
        verify_distribution_version(
            args.dist,
            tag,
            require_dev=args.require_dev,
            require_sdist=not args.allow_wheels_only,
        )
    )


if __name__ == "__main__":
    main()
