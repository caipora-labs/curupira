"""Install one project's wheel from dist/ and smoke-test it outside the repository."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version


def main(argv: list[str] | None = None) -> None:
    """Install the project's wheel into a temporary venv and run smoke checks."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument(
        "--project",
        default="curupira",
        help="Distribution to install from dist/; CLI and config checks run only for curupira",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Run `curupira --config PATH validate` after installation (curupira only)",
    )
    parser.add_argument(
        "--expected-version",
        default="",
        help="Require the module __version__ and CLI --version to equal this PEP 440 version",
    )
    args = parser.parse_args(argv)

    dist = args.dist.resolve()
    wheel = select_wheel(dist, args.project)
    module = args.project.replace("-", "_")
    is_cli = canonicalize_name(args.project) == "curupira"
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

        _run([str(pip), "install", "--only-binary=:all:", "--find-links", str(dist), str(wheel)])
        found = _import_version(python, module)
        if args.expected_version:
            _require_same_version(f"{module}.__version__", found, args.expected_version)
        if is_cli:
            _assert_optional_extensions_absent(python)
            curupira = _venv_executable(venv_dir, "curupira")
            curu = _venv_executable(venv_dir, "curu")
            _assert_cli(curupira, "curupira", args.expected_version or None)
            _assert_cli(curu, "curu", args.expected_version or None)
        if is_cli and config is not None:
            # Example configs launch via `uvx --from curupira-plugins`; expose dist/
            # so uvx can resolve the wheel without hitting the network.
            env = _cli_env()
            env["UV_FIND_LINKS"] = str(dist)
            path = env.get("PATH", "")
            local_bin = Path.home() / ".local" / "bin"
            if local_bin.is_dir():
                env["PATH"] = f"{local_bin}{os.pathsep}{path}"
            _run_env(
                [str(curupira), "--config", str(config), "validate"],
                env=env,
            )
            print(f"validated configuration {config}")
        print(f"smoke-tested {wheel.name}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def select_wheel(dist: Path, project: str) -> Path:
    """Return the best wheel for ``project`` in ``dist`` that installs on this interpreter."""
    wheels = sorted(dist.glob("*.whl"))
    if not wheels:
        message = f"No wheels found in {dist}"
        raise SystemExit(message)

    try:
        from packaging.tags import sys_tags
    except ImportError as exc:
        message = "packaging is required to select a platform wheel"
        raise SystemExit(message) from exc

    name = canonicalize_name(project)
    supported = list(sys_tags())
    ranked: list[tuple[int, Path]] = []
    for wheel in wheels:
        distribution, _version, _build, tags = parse_wheel_filename(wheel.name)
        if distribution != name:
            continue
        for index, tag in enumerate(supported):
            if tag in tags:
                ranked.append((index, wheel))
                break
    if not ranked:
        names = ", ".join(wheel.name for wheel in wheels)
        message = f"No {project} wheel in {dist} matches this platform; found: {names}"
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
    _run_env(command, env=_cli_env())


def _run_env(command: list[str], *, env: dict[str, str]) -> None:
    subprocess.run(command, check=True, cwd=tempfile.gettempdir(), env=env)


def _import_version(python: Path, module: str) -> str:
    """Import ``module`` from the venv and return its ``__version__`` string."""
    result = subprocess.run(
        [str(python), "-c", f"import {module}\nprint({module}.__version__)"],
        check=True,
        cwd=tempfile.gettempdir(),
        capture_output=True,
        text=True,
        env=_cli_env(),
    )
    return result.stdout.strip()


def _require_same_version(label: str, found: str, expected: str) -> None:
    """Compare PEP 440 versions so ``0.1.0.dev0`` and ``0.1.0dev0`` are equal."""
    if Version(found) != Version(expected):
        message = f"{label} {found!r} != {expected!r}"
        raise SystemExit(message)


def _assert_optional_extensions_absent(python: Path) -> None:
    """Base wheel must not pull in SDK or the official trigger package."""
    script = """
import importlib.util

for name in ("curupira_sdk", "curupira_plugins"):
    if importlib.util.find_spec(name) is not None:
        raise SystemExit(f"unexpected dependency installed: {name}")
print("optional extensions absent")
"""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    subprocess.run(
        [str(python), "-c", script],
        check=True,
        cwd=tempfile.gettempdir(),
        env=env,
    )


def _assert_cli(executable: Path, program: str, expected_version: str | None) -> None:
    help_text = subprocess.run(
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

    version_text = subprocess.run(
        [str(executable), "--version"],
        check=True,
        cwd=tempfile.gettempdir(),
        capture_output=True,
        text=True,
        env=_cli_env(),
    ).stdout.strip()
    prefix = f"{program} "
    if not version_text.startswith(prefix):
        message = f"unexpected {program} --version: {version_text!r}"
        raise SystemExit(message)
    if expected_version is None:
        return
    # The Rust binary reports its SemVer (0.3.0-dev0); compare it as PEP 440 like the wheel.
    _require_same_version(
        f"{program} --version", version_text.removeprefix(prefix), expected_version
    )


def _cli_env() -> dict[str, str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return env


if __name__ == "__main__":
    main()
