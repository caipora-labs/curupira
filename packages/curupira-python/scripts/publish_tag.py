"""Resolve a ``publish/<project>/<version>`` tag to the project and version it releases.

The git tag is the only source of a release version. The Python packages read it through
hatch-vcs, and ``stamp_release_version.py`` writes it into the Rust crate. Prints
``key=value`` lines so the workflow can append them to ``GITHUB_OUTPUT``.
"""

from __future__ import annotations

import argparse
import os
import re

from packaging.version import InvalidVersion, Version

PROJECTS = frozenset({"curupira", "curupira-sdk", "curupira-plugins"})
TAG = re.compile(r"publish/(?P<project>[a-z0-9-]+)/(?P<version>[^/\s]+)")
CARGO_PRE_RELEASE = {"a": "alpha", "b": "beta", "rc": "rc"}


def parse_tag(tag: str) -> tuple[str, Version]:
    """Return the project and PEP 440 version named by a ``publish/<project>/<version>`` tag."""
    match = TAG.fullmatch(tag)
    if match is None:
        message = f"Expected a tag publish/<project>/<version>, got {tag!r}"
        raise SystemExit(message)
    project = match["project"]
    if project not in PROJECTS:
        message = f"Unknown project {project!r}; expected one of {sorted(PROJECTS)}"
        raise SystemExit(message)
    try:
        version = Version(match["version"])
    except InvalidVersion as exc:
        message = f"Tag {tag!r} does not name a PEP 440 version"
        raise SystemExit(message) from exc
    return project, version


def cargo_version(version: Version) -> str:
    """Return the SemVer form Cargo accepts, e.g. ``0.3.0.dev0`` becomes ``0.3.0-dev0``."""
    release = ".".join(str(part) for part in version.release)
    if version.pre is not None:
        letter, number = version.pre
        return f"{release}-{CARGO_PRE_RELEASE[letter]}.{number}"
    if version.dev is not None:
        return f"{release}-dev{version.dev}"
    return release


def main(argv: list[str] | None = None) -> None:
    """Print the release outputs for the tag, defaulting to ``GITHUB_REF_NAME``."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tag", nargs="?", default=os.environ.get("GITHUB_REF_NAME", ""))
    args = parser.parse_args(argv)
    project, version = parse_tag(args.tag)
    print(f"project={project}")
    print(f"version={version}")
    print(f"cargo_version={cargo_version(version)}")
    print(f"prerelease={str(version.is_prerelease).lower()}")


if __name__ == "__main__":
    main()
