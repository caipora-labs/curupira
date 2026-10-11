"""Pure-data interactive launch recipes for coding-agent CLIs in a PTY."""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from pathlib import Path

from pydantic import Field

from curupira.models.base import ValidatedModel

_PTY_ENV_ALLOWLIST = ("PATH", "HOME", "LANG", "USER", "SHELL")


class InteractiveLaunchSpec(ValidatedModel):
    """Recipe for starting a coding-agent CLI interactively inside a PTY.

    This is pure data: Curupira does not launch a process from this model. A later
    orchestrator (embedded terminal panel) consumes the fields.

    Attributes:
        argv: Full argument vector with the executable as ``argv[0]``.
        env: Extra environment variables only. Callers merge them through
            :func:`default_pty_env`; secrets and host tokens must never appear here.
        cwd: Working directory for the interactive session.
        notes: Human-readable caveats when a flag or prompt could not be applied.
    """

    argv: tuple[str, ...]
    env: dict[str, str] = Field(default_factory=dict)
    cwd: Path
    notes: tuple[str, ...] = ()


def default_pty_env(*, extra: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a PTY environment from an allowlist of host variables.

    Copies ``PATH``, ``HOME``, ``LANG``, ``USER``, and ``SHELL`` from ``os.environ``
    when present, then always sets ``TERM=xterm-256color`` and
    ``COLORTERM=truecolor``. Unknown host variables (including secrets such as
    ``AWS_SECRET_ACCESS_KEY``) are never forwarded. ``extra`` overlays additional
    values from an :class:`InteractiveLaunchSpec`.
    """
    env = {key: os.environ[key] for key in _PTY_ENV_ALLOWLIST if key in os.environ}
    env["TERM"] = "xterm-256color"
    env["COLORTERM"] = "truecolor"
    if extra:
        env.update(dict(extra))
    return env


def spec_available(spec: InteractiveLaunchSpec) -> bool:
    """Return whether the executable in ``spec.argv[0]`` is findable on ``PATH``."""
    if not spec.argv:
        return False
    return shutil.which(spec.argv[0]) is not None
