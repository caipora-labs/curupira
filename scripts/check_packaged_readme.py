"""Build distributions, reject stale OpsCli branding, and run twine check.

PyPI renders the packaged README / metadata long description. The retired product
name OpsCli must not appear there (case-insensitive). Run from the repository
root:

    uv run --no-sync python scripts/check_packaged_readme.py
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tarfile
import zipfile
from email.message import Message
from email.parser import Parser
from pathlib import Path

FORBIDDEN = "opscli"


def assert_no_opscli_in_distributions(dist: Path) -> None:
    """Fail when any built wheel or sdist carries OpsCli in README or metadata."""
    wheels = sorted(dist.glob("*.whl"))
    sources = sorted(dist.glob("*.tar.gz"))
    if not wheels:
        message = f"Expected at least one wheel in {dist}"
        raise SystemExit(message)
    if not sources:
        message = f"Expected at least one sdist in {dist}"
        raise SystemExit(message)
    for wheel in wheels:
        _assert_texts_clean(wheel, _wheel_readme_and_metadata(wheel))
    for source in sources:
        _assert_texts_clean(source, _sdist_readme_and_metadata(source))


def _assert_texts_clean(archive: Path, labeled_texts: list[tuple[str, str]]) -> None:
    for label, text in labeled_texts:
        if FORBIDDEN in text.lower():
            message = (
                f"{archive.name}: {label} contains {FORBIDDEN!r} "
                "(retired OpsCli branding must not ship in release metadata)"
            )
            raise SystemExit(message)


def _wheel_readme_and_metadata(wheel: Path) -> list[tuple[str, str]]:
    texts: list[tuple[str, str]] = []
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(
            (name for name in archive.namelist() if name.endswith(".dist-info/METADATA")),
            None,
        )
        if metadata_name is None:
            message = f"Missing METADATA in {wheel}"
            raise SystemExit(message)
        metadata = Parser().parsestr(archive.read(metadata_name).decode())
        texts.append((f"{metadata_name} long description", _long_description(metadata)))
        for name in archive.namelist():
            basename = Path(name).name.lower()
            if basename.startswith("readme"):
                texts.append((name, archive.read(name).decode()))
    return texts


def _sdist_readme_and_metadata(source: Path) -> list[tuple[str, str]]:
    texts: list[tuple[str, str]] = []
    with tarfile.open(source, "r:gz") as archive:
        metadata_member = next(
            (member for member in archive.getmembers() if member.name.endswith("/PKG-INFO")),
            None,
        )
        if metadata_member is None:
            message = f"Missing PKG-INFO in {source}"
            raise SystemExit(message)
        extracted = archive.extractfile(metadata_member)
        if extracted is None:
            message = f"Cannot read PKG-INFO from {source}"
            raise SystemExit(message)
        metadata = Parser().parsestr(extracted.read().decode())
        texts.append((f"{metadata_member.name} long description", _long_description(metadata)))
        for member in archive.getmembers():
            if not member.isfile():
                continue
            basename = Path(member.name).name.lower()
            if not basename.startswith("readme"):
                continue
            file_obj = archive.extractfile(member)
            if file_obj is None:
                message = f"Cannot read {member.name} from {source}"
                raise SystemExit(message)
            texts.append((member.name, file_obj.read().decode()))
    return texts


def _long_description(metadata: Message) -> str:
    """Return the metadata payload PyPI shows as the project description."""
    payload = metadata.get_payload()
    if isinstance(payload, str):
        return payload
    description = metadata.get("Description")
    return description or ""


def _build_distributions(dist: Path) -> None:
    dist.mkdir(parents=True, exist_ok=True)
    for stale in (*dist.glob("*.whl"), *dist.glob("*.tar.gz")):
        stale.unlink()
    uv = shutil.which("uv")
    if uv is None:
        message = "uv is required on PATH to build distributions"
        raise SystemExit(message)
    subprocess.run([uv, "build", "--out-dir", str(dist)], check=True)  # noqa: S603


def _twine_check(dist: Path) -> None:
    artifacts = [
        str(path) for path in (*sorted(dist.glob("*.whl")), *sorted(dist.glob("*.tar.gz")))
    ]
    if not artifacts:
        message = f"No distributions to check in {dist}"
        raise SystemExit(message)
    subprocess.run(  # noqa: S603
        [sys.executable, "-m", "twine", "check", *artifacts],
        check=True,
    )


def main(argv: list[str] | None = None) -> None:
    """Build (optional), reject OpsCli in packaged README/metadata, then twine check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument(
        "--no-build",
        action="store_true",
        help="Check existing artifacts in --dist without running uv build",
    )
    parser.add_argument(
        "--no-twine",
        action="store_true",
        help="Skip twine check after the OpsCli branding guard",
    )
    args = parser.parse_args(argv)
    dist = args.dist.resolve()
    if not args.no_build:
        _build_distributions(dist)
    assert_no_opscli_in_distributions(dist)
    print(f"no {FORBIDDEN!r} in packaged README or metadata under {dist}")
    if not args.no_twine:
        _twine_check(dist)
        print(f"twine check passed for {dist}")


if __name__ == "__main__":
    main()
