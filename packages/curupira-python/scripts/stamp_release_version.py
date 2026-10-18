"""Write a release version into the files that cannot read the git tag themselves.

hatch-vcs gives the Python packages their version from the tag. The Rust crate reads its
version from Cargo.toml, npm packages read ``package.json``, and the official plugin
manifest is a static TOML file, so the release workflow stamps those before building.
Only the publish workflow runs this. The npm version uses the Cargo semver form
(``0.3.0.dev0`` becomes ``0.3.0-dev0``).
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from packaging.version import Version
from publish_tag import cargo_version

VERSION_LINE = re.compile(r'^version = "[^"]*"$', re.MULTILINE)
# Files stamped per Python project. The Python SDK packages use hatch-vcs and need no stamp.
STAMPED = {
    "curupira": (Path("packages/curupira-core/Cargo.toml"), 1, cargo_version),
    "curupira-plugins": (
        Path("packages/curupira-python-plugins/curupira-extension.toml"),
        0,
        str,
    ),
}
# The npm CLI ships the same Rust binary, so it takes the Cargo form of the tag.
NPM_MANIFEST = Path("packages/curupira-npm/package.json")
NPM_SDK_MANIFEST = Path("packages/curupira-js-sdk/package.json")
NPM_SDK_LOCKFILE = Path("packages/curupira-js-sdk/package-lock.json")


def stamp(project: str, version: Version, root: Path = Path()) -> list[Path]:
    """Write ``version`` into the project's stamped files and return the files changed."""
    changed: list[Path] = []
    if project in STAMPED:
        changed.append(_stamp_version_line(project, version, root))
    if project == "curupira":
        changed.append(_stamp_npm_manifest(root, cargo_version(version)))
    if project == "curupira-js-sdk":
        changed.extend(_stamp_npm_sdk_manifests(root, cargo_version(version)))
    return changed


def _stamp_version_line(project: str, version: Version, root: Path) -> Path:
    relative, count, render = STAMPED[project]
    path = root / relative
    text = path.read_text(encoding="utf-8")
    value = render(version)
    stamped, replaced = VERSION_LINE.subn(f'version = "{value}"', text, count=count)
    if replaced == 0:
        message = f"No version line found in {path}"
        raise SystemExit(message)
    path.write_text(stamped, encoding="utf-8")
    return path


def _stamp_npm_manifest(root: Path, version: str) -> Path:
    """Write the release version into the npm CLI manifest and its platform dependencies."""
    path = root / NPM_MANIFEST
    if not path.is_file():
        message = f"Missing npm manifest {path}"
        raise SystemExit(message)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["version"] = version
    optional = manifest.get("optionalDependencies")
    if isinstance(optional, dict):
        for name in optional:
            optional[name] = version
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


def _stamp_npm_sdk_manifests(root: Path, version: str) -> list[Path]:
    """Write the version into both npm manifests for the JavaScript SDK."""
    manifest_path = root / NPM_SDK_MANIFEST
    lockfile_path = root / NPM_SDK_LOCKFILE
    for path in (manifest_path, lockfile_path):
        if not path.is_file():
            message = f"Missing npm manifest {path}"
            raise SystemExit(message)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = version
    lockfile = json.loads(lockfile_path.read_text(encoding="utf-8"))
    lockfile["version"] = version
    lockfile["packages"][""]["version"] = version
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    lockfile_path.write_text(json.dumps(lockfile, indent=2) + "\n", encoding="utf-8")
    return [manifest_path, lockfile_path]


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
