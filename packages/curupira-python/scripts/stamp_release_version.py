"""Write a release version into the files that cannot read the git tag themselves.

hatch-vcs gives the Python packages their version from the tag. The Rust crate reads its
version from Cargo.toml, and the official plugin manifest is a static TOML file, so the
release workflow stamps both before building. Only the publish workflow runs this.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from packaging.version import Version
from publish_tag import cargo_version

VERSION_LINE = re.compile(r'^version = "[^"]*"$', re.MULTILINE)
# Files stamped per project. The SDK needs none: hatch-vcs reads its tag directly.
STAMPED = {
    "curupira": (Path("packages/curupira-core/Cargo.toml"), 1, cargo_version),
    "curupira-plugins": (
        Path("packages/curupira-python-plugins/curupira-extension.toml"),
        0,
        str,
    ),
}


def stamp(project: str, version: Version, root: Path = Path()) -> list[Path]:
    """Write ``version`` into the project's stamped files and return the files changed."""
    if project not in STAMPED:
        return []
    relative, count, render = STAMPED[project]
    path = root / relative
    text = path.read_text(encoding="utf-8")
    value = render(version)
    stamped, replaced = VERSION_LINE.subn(f'version = "{value}"', text, count=count)
    if replaced == 0:
        message = f"No version line found in {path}"
        raise SystemExit(message)
    path.write_text(stamped, encoding="utf-8")
    return [path]


def main(argv: list[str] | None = None) -> None:
    """Stamp the release version for one project."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    for path in stamp(args.project, Version(args.version)):
        print(f"stamped {path}")


if __name__ == "__main__":
    main()
