"""Install a wheel from dist/ and smoke-test the CLI entry points."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path


def main(argv: list[str] | None = None) -> None:
    """Install the matching wheel into a temporary venv and run smoke checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument(
        "--config",
        type=Path,
        help="Run `curupira --config PATH validate` after installation",
    )
    parser.add_argument(
        "--expected-version",
        default="",
        help="Require curupira.__version__ and CLI --version to match this string",
    )
    args = parser.parse_args(argv)

    dist = args.dist.resolve()
    wheel = select_wheel(dist)
    config = args.config.resolve() if args.config is not None else None
    if config is not None and not config.is_file():
        message = f"Configuration file not found: {config}"
        raise SystemExit(message)

    work = Path(tempfile.mkdtemp(prefix="curupira-smoke-"))
    try:
        venv_dir = work / "venv"
        venv.create(venv_dir, with_pip=True, clear=True)
        pip = _venv_executable(venv_dir, "pip")
        python = _venv_executable(venv_dir, "python")
        curupira = _venv_executable(venv_dir, "curupira")
        curu = _venv_executable(venv_dir, "curu")

        _run([str(pip), "install", "--only-binary=:all:", str(wheel)])
        _assert_import(python, args.expected_version or None)
        _assert_cli(curupira, "curupira", args.expected_version or None)
        _assert_cli(curu, "curu", args.expected_version or None)
        if config is not None:
            _run([str(curupira), "--config", str(config), "validate"])
            print(f"validated configuration {config}")
        print(f"smoke-tested {wheel.name}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def select_wheel(dist: Path) -> Path:
    """Return the best wheel in ``dist`` that is installable on this interpreter."""
    wheels = sorted(dist.glob("*.whl"))
    if not wheels:
        message = f"No wheels found in {dist}"
        raise SystemExit(message)

    try:
        from packaging.tags import sys_tags
        from packaging.utils import parse_wheel_filename
    except ImportError as exc:
        message = "packaging is required to select a platform wheel"
        raise SystemExit(message) from exc

    supported = list(sys_tags())
    ranked: list[tuple[int, Path]] = []
    for wheel in wheels:
        _name, _version, _build, tags = parse_wheel_filename(wheel.name)
        for index, tag in enumerate(supported):
            if tag in tags:
                ranked.append((index, wheel))
                break
    if not ranked:
        names = ", ".join(wheel.name for wheel in wheels)
        message = f"No wheel in {dist} matches this platform; found: {names}"
        raise SystemExit(message)
    ranked.sort(key=lambda item: item[0])
    return ranked[0][1]


def _venv_executable(venv_dir: Path, name: str) -> Path:
    if sys.platform == "win32":
        scripts = venv_dir / "Scripts"
        for candidate in (scripts / f"{name}.exe", scripts / name):
            if candidate.exists() or name in {"pip", "python"}:
                return candidate
        return scripts / f"{name}.exe"
    return venv_dir / "bin" / name


def _run(command: list[str]) -> None:
    env = os.environ.copy()
    # Avoid importing the repository checkout ahead of the installed package.
    env.pop("PYTHONPATH", None)
    subprocess.run(command, check=True, cwd=tempfile.gettempdir(), env=env)  # noqa: S603


def _assert_import(python: Path, expected_version: str | None) -> None:
    script = """
import os
import curupira

expected = os.environ.get("CURUPIRA_EXPECTED_VERSION", "")
if expected and curupira.__version__ != expected:
    raise SystemExit(f"installed version {curupira.__version__!r} != {expected!r}")
print(curupira.__version__)
"""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    if expected_version:
        env["CURUPIRA_EXPECTED_VERSION"] = expected_version
    subprocess.run(  # noqa: S603
        [str(python), "-c", script],
        check=True,
        cwd=tempfile.gettempdir(),
        env=env,
    )


def _assert_cli(executable: Path, program: str, expected_version: str | None) -> None:
    help_text = subprocess.run(  # noqa: S603
        [str(executable), "--help"],
        check=True,
        cwd=tempfile.gettempdir(),
        capture_output=True,
        text=True,
        env=_cli_env(),
    ).stdout
    # Argparse used "usage:"; Typer/Click use "Usage:".
    if f"usage: {program}" not in help_text.lower():
        message = f"{program} --help missing usage line"
        raise SystemExit(message)

    version_text = subprocess.run(  # noqa: S603
        [str(executable), "--version"],
        check=True,
        cwd=tempfile.gettempdir(),
        capture_output=True,
        text=True,
        env=_cli_env(),
    ).stdout.strip()
    if expected_version is None:
        if not version_text.startswith(f"{program} "):
            message = f"unexpected {program} --version: {version_text!r}"
            raise SystemExit(message)
        return
    expected = f"{program} {expected_version}"
    if version_text != expected:
        message = f"{program} --version {version_text!r} != {expected!r}"
        raise SystemExit(message)


def _cli_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return env


if __name__ == "__main__":
    main()
