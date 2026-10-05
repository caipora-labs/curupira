"""Version-control operations shared by repository hosting providers."""

from __future__ import annotations

import asyncio
import shutil
from abc import ABC, abstractmethod
from asyncio import to_thread
from pathlib import Path

from gh_dispatch.clients.process import AsyncProcessRunner
from gh_dispatch.errors import CliExecutionError, CliOutputError, WorkspacePathError
from gh_dispatch.models.base import NonEmptyString, ValidatedModel
from gh_dispatch.models.process import CommandRequest, ProcessResult


class CheckoutRequest(ValidatedModel):
    """A requested repository checkout."""

    repo: NonEmptyString
    destination: Path


class Checkout(ValidatedModel):
    """A prepared repository checkout."""

    repo: NonEmptyString
    path: Path
    cloned: bool


class VersionControl(ABC):
    """Provider-specific clone operation with shared Git checkout behavior."""

    def __init__(self, runner: AsyncProcessRunner | None = None) -> None:
        self._runner = runner or AsyncProcessRunner()
        self._clone_locks: dict[Path, asyncio.Lock] = {}
        self._worktree_locks: dict[Path, asyncio.Lock] = {}

    @abstractmethod
    async def clone(self, repo: str, destination: Path) -> None:
        """Clone a repository into destination using the provider's native mechanism."""

    async def ensure_checkout(self, request: CheckoutRequest) -> Checkout:
        """Reuse a Git checkout or clone it once, serialized by destination."""
        destination = request.destination.expanduser().resolve()
        lock = self._clone_locks.setdefault(destination, asyncio.Lock())
        async with lock:
            if await asyncio.to_thread(_is_git_checkout, destination):
                return Checkout(repo=request.repo, path=destination, cloned=False)
            if await asyncio.to_thread(destination.exists):
                raise WorkspacePathError(
                    f"workspace destination exists but is not a Git checkout: {destination}"
                )
            try:
                await asyncio.to_thread(destination.parent.mkdir, parents=True, exist_ok=True)
            except OSError as error:
                raise WorkspacePathError(
                    f"cannot create workspace directory {destination.parent}: {error}"
                ) from error
            await self.clone(request.repo, destination)
            if not await asyncio.to_thread(_is_git_checkout, destination):
                raise CliOutputError(
                    f"clone reported success, but no Git checkout was created at {destination}"
                )
            return Checkout(repo=request.repo, path=destination, cloned=True)

    async def run_setup_script(
        self,
        checkout: Checkout,
        script: str,
        *,
        timeout_seconds: float | None = None,
        max_output_bytes: int = 1_000_000,
    ) -> ProcessResult:
        """Run a repository-relative setup executable after a fresh clone."""
        try:
            result = await self._runner.run(
                CommandRequest(
                    executable=str(checkout.path / script),
                    cwd=checkout.path,
                    timeout=timeout_seconds,
                    max_output_bytes=max_output_bytes,
                )
            )
        except Exception:
            if checkout.cloned:
                await to_thread(shutil.rmtree, checkout.path, True)
            raise
        if result.returncode and checkout.cloned:
            await to_thread(shutil.rmtree, checkout.path, True)
        return result

    async def ensure_worktree(
        self, checkout: Checkout, *, automation_id: str, task_type: str, number: int
    ) -> Path:
        """Create or reuse the task worktree from origin's configured default branch."""
        base = checkout.path
        lock = self._worktree_locks.setdefault(base, asyncio.Lock())
        async with lock:
            target = (
                base.with_name(f"{base.name}.worktrees") / automation_id / f"{task_type}-{number}"
            )
            if target.is_dir():
                return target
            fetch = await self._runner.run(
                CommandRequest(executable="git", arguments=("fetch", "origin"), cwd=base)
            )
            if fetch.returncode:
                raise CliExecutionError("git fetch", fetch.returncode, fetch.stderr)
            default = await self._runner.run(
                CommandRequest(
                    executable="git",
                    arguments=("symbolic-ref", "refs/remotes/origin/HEAD"),
                    cwd=base,
                )
            )
            if default.returncode:
                raise CliExecutionError("git symbolic-ref", default.returncode, default.stderr)
            target.parent.mkdir(parents=True, exist_ok=True)
            branch = f"gh-dispatch/{automation_id}/{task_type}-{number}"
            result = await self._runner.run(
                CommandRequest(
                    executable="git",
                    arguments=(
                        "worktree",
                        "add",
                        "-b",
                        branch,
                        str(target),
                        default.stdout.strip(),
                    ),
                    cwd=base,
                )
            )
            if result.returncode:
                raise CliExecutionError("git worktree add", result.returncode, result.stderr)
            return target

    async def remove_worktree(
        self, checkout: Checkout, *, automation_id: str, task_type: str, number: int
    ) -> None:
        """Remove a task worktree and its local branch."""
        base = checkout.path
        lock = self._worktree_locks.setdefault(base, asyncio.Lock())
        async with lock:
            target = (
                base.with_name(f"{base.name}.worktrees") / automation_id / f"{task_type}-{number}"
            )
            for arguments in (
                ("worktree", "remove", "--force", str(target)),
                ("branch", "-D", f"gh-dispatch/{automation_id}/{task_type}-{number}"),
            ):
                result = await self._runner.run(
                    CommandRequest(executable="git", arguments=arguments, cwd=base)
                )
                if result.returncode:
                    raise CliExecutionError("git " + arguments[0], result.returncode, result.stderr)


def _is_git_checkout(path: Path) -> bool:
    return path.is_dir() and (path / ".git").exists()
