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
    hits: list[str] = []
    for wheel in wheels:
        hits.extend(_opscli_hits(wheel, _wheel_readme_and_metadata(wheel)))
    for source in sources:
        hits.extend(_opscli_hits(source, _sdist_readme_and_metadata(source)))
    if hits:
        detail = "\n".join(hits)
        message = f"{detail}\n(retired OpsCli branding must not ship in release metadata)"
        raise SystemExit(message)


def _opscli_hits(archive: Path, members: list[tuple[str, str, int]]) -> list[str]:
    """Return ``archive:member:line: snippet`` for every OpsCli line.

    ``line_offset`` shifts description-body lines so numbers match the member
    file (METADATA / PKG-INFO headers plus the blank separator).
    """
    hits: list[str] = []
    for member, text, line_offset in members:
        for index, line in enumerate(text.splitlines(), start=1):
            if FORBIDDEN not in line.lower():
                continue
            snippet = line.strip()
            if len(snippet) > 80:
                snippet = f"{snippet[:77]}..."
            hits.append(f"{archive.name}:{member}:{line_offset + index}: {snippet}")
    return hits


def _wheel_readme_and_metadata(wheel: Path) -> list[tuple[str, str, int]]:
    texts: list[tuple[str, str, int]] = []
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(
            (name for name in archive.namelist() if name.endswith(".dist-info/METADATA")),
            None,
        )
        if metadata_name is None:
            message = f"Missing METADATA in {wheel}"
            raise SystemExit(message)
        raw = archive.read(metadata_name).decode()
        metadata = Parser().parsestr(raw)
        texts.append((metadata_name, _long_description(metadata), _description_line_offset(raw)))
        for name in archive.namelist():
            basename = Path(name).name.lower()
            if basename.startswith("readme"):
                texts.append((name, archive.read(name).decode(), 0))
    return texts


def _sdist_readme_and_metadata(source: Path) -> list[tuple[str, str, int]]:
    texts: list[tuple[str, str, int]] = []
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
        raw = extracted.read().decode()
        metadata = Parser().parsestr(raw)
        texts.append(
            (
                metadata_member.name,
                _long_description(metadata),
                _description_line_offset(raw),
            )
        )
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
            texts.append((member.name, file_obj.read().decode(), 0))
    return texts


def _long_description(metadata: Message) -> str:
    """Return the metadata payload PyPI shows as the project description."""
    payload = metadata.get_payload()
    if isinstance(payload, str):
        return payload
    description = metadata.get("Description")
    return description or ""


def _description_line_offset(raw_metadata: str) -> int:
    """Return how many member lines precede the long-description body."""
    for index, line in enumerate(raw_metadata.splitlines()):
        if line == "":
            return index + 1
    return 0


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
    print(f"no {FORBIDDEN!r} in packaged README or metadata under {dist}", flush=True)
    if not args.no_twine:
        _twine_check(dist)
        print(f"twine check passed for {dist}", flush=True)


if __name__ == "__main__":
    main()
