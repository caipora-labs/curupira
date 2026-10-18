"""Unit tests for the release scripts: tag parsing, version stamping and distribution checks."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import tarfile
import zipfile
from pathlib import Path
from types import ModuleType

import pytest
from packaging.version import Version

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(name: str) -> ModuleType:
    # Scripts import their siblings (stamp_release_version imports publish_tag) by name.
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


publish_tag = _load("publish_tag")
stamp_release_version = _load("stamp_release_version")
verify_dist_version = _load("verify_dist_version")


def test_parse_tag_reads_project_and_pep440_version() -> None:
    project, version = publish_tag.parse_tag("publish/curupira-sdk/0.1.0dev0")
    assert project == "curupira-sdk"
    assert version == Version("0.1.0.dev0")


def test_parse_tag_accepts_the_independent_javascript_sdk() -> None:
    project, version = publish_tag.parse_tag("publish/curupira-js-sdk/0.2.0")
    assert project == "curupira-js-sdk"
    assert version == Version("0.2.0")


@pytest.mark.parametrize(
    "tag",
    [
        "v0.2.0",
        "publish/curupira/",
        "publish/unknown-package/1.0.0",
        "publish/curupira/not-a-version",
    ],
)
def test_parse_tag_rejects_malformed_tags(tag: str) -> None:
    with pytest.raises(SystemExit):
        publish_tag.parse_tag(tag)


@pytest.mark.parametrize(
    ("version", "expected"),
    [
        ("0.3.0.dev0", "0.3.0-dev0"),
        ("1.0.0", "1.0.0"),
        ("1.0.0rc1", "1.0.0-rc.1"),
    ],
)
def test_cargo_version_is_semver(version: str, expected: str) -> None:
    assert publish_tag.cargo_version(Version(version)) == expected


def test_stamp_writes_crate_and_npm_versions(tmp_path: Path) -> None:
    cargo = tmp_path / "packages/curupira-core/Cargo.toml"
    cargo.parent.mkdir(parents=True)
    cargo.write_text(
        '[package]\nname = "curupira"\nversion = "0.2.0"\n\n[dependencies.serde]\nversion = "1"\n',
        encoding="utf-8",
    )
    npm = tmp_path / "packages/curupira-npm/package.json"
    npm.parent.mkdir(parents=True)
    npm.write_text(
        json.dumps(
            {
                "name": "curupira",
                "version": "0.2.0",
                "optionalDependencies": {
                    "@caipora-labs/curupira-linux-x64": "0.2.0",
                    "@caipora-labs/curupira-win32-arm64": "0.2.0",
                },
            }
        ),
        encoding="utf-8",
    )
    stamp_release_version.stamp("curupira", Version("0.3.0.dev0"), tmp_path)
    text = cargo.read_text(encoding="utf-8")
    assert 'version = "0.3.0-dev0"' in text
    assert 'version = "1"' in text
    manifest = json.loads(npm.read_text(encoding="utf-8"))
    assert manifest["version"] == "0.3.0-dev0"
    assert manifest["optionalDependencies"] == {
        "@caipora-labs/curupira-linux-x64": "0.3.0-dev0",
        "@caipora-labs/curupira-win32-arm64": "0.3.0-dev0",
    }


def test_stamp_writes_every_plugin_manifest_version(tmp_path: Path) -> None:
    manifest = tmp_path / "packages/curupira-python-plugins/curupira-extension.toml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        'name = "curupira-plugins"\nversion = "0.2.0"\n\n[package]\nversion = "0.2.0"\n',
        encoding="utf-8",
    )
    stamp_release_version.stamp("curupira-plugins", Version("0.1.0.dev0"), tmp_path)
    assert manifest.read_text(encoding="utf-8").count('version = "0.1.0.dev0"') == 2


def test_stamp_writes_independent_javascript_sdk_version(tmp_path: Path) -> None:
    manifest = tmp_path / "packages/curupira-js-sdk/package.json"
    lockfile = manifest.with_name("package-lock.json")
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        json.dumps({"name": "@caipora-labs/curupira-sdk", "version": "0.1.0-dev.0"}),
        encoding="utf-8",
    )
    lockfile.write_text(
        json.dumps(
            {
                "name": "@caipora-labs/curupira-sdk",
                "version": "0.1.0-dev.0",
                "packages": {"": {"name": "@caipora-labs/curupira-sdk", "version": "0.1.0-dev.0"}},
            }
        ),
        encoding="utf-8",
    )

    stamp_release_version.stamp("curupira-js-sdk", Version("0.2.0.dev1"), tmp_path)

    stamped = json.loads(manifest.read_text(encoding="utf-8"))
    assert stamped == {"name": "@caipora-labs/curupira-sdk", "version": "0.2.0-dev1"}
    locked = json.loads(lockfile.read_text(encoding="utf-8"))
    assert locked["version"] == "0.2.0-dev1"
    assert locked["packages"][""]["version"] == "0.2.0-dev1"


def _wheel(path: Path, name: str, version: str) -> Path:
    dist_info = f"{name}-{version}.dist-info"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            f"{dist_info}/METADATA", f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n"
        )
    return path


def _sdist(path: Path, name: str, version: str) -> Path:
    payload = f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n".encode()
    with tarfile.open(path, "w:gz") as archive:
        info = tarfile.TarInfo(f"{name}-{version}/PKG-INFO")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    return path


def test_verify_checks_only_the_requested_project(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    _wheel(dist / "curupira_sdk-0.1.0.dev0-py3-none-any.whl", "curupira_sdk", "0.1.0.dev0")
    _sdist(dist / "curupira_sdk-0.1.0.dev0.tar.gz", "curupira_sdk", "0.1.0.dev0")
    # Another package in the same directory may carry a different version.
    _wheel(dist / "curupira_plugins-0.2.0-py3-none-any.whl", "curupira_plugins", "0.2.0")

    paths = verify_dist_version.verify_distribution_version(dist, "curupira-sdk", "0.1.0dev0")
    assert sorted(path.name for path in paths) == [
        "curupira_sdk-0.1.0.dev0-py3-none-any.whl",
        "curupira_sdk-0.1.0.dev0.tar.gz",
    ]


def test_verify_rejects_a_distribution_built_from_another_version(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    _wheel(dist / "curupira_sdk-0.1.0.dev0-py3-none-any.whl", "curupira_sdk", "0.1.0.dev0")
    _sdist(dist / "curupira_sdk-0.1.0.dev0.tar.gz", "curupira_sdk", "0.1.0.dev0")

    with pytest.raises(SystemExit):
        verify_dist_version.verify_distribution_version(dist, "curupira-sdk", "0.1.0.dev1")
