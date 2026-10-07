"""Tests for shared version-control checkout behavior using local Git repositories."""

import hashlib
import subprocess
from collections.abc import Awaitable, Callable
from pathlib import Path

import pytest
from typing_extensions import override

from curupi.clients.process import AsyncProcessRunner
from curupi.errors import WorkspacePathError
from curupi.models import CommandRequest, ProcessResult
from curupi.vcs import Checkout, CheckoutRequest, VersionControl


class LocalGitVersionControl(VersionControl):
    """Fake provider that clones a temporary local repository without ``gh``."""

    def __init__(self) -> None:
        super().__init__()
        self.clone_count = 0

    @override
    async def clone(self, repo: str, destination: Path) -> None:
        self.clone_count += 1
        result = await self._runner.run(
            CommandRequest(executable="git", arguments=("clone", repo, str(destination)))
        )
        assert result.returncode == 0, result.stderr
        result = await self._runner.run(
            CommandRequest(
                executable="git",
                arguments=("remote", "set-head", "origin", "main"),
                cwd=destination,
            )
        )
        assert result.returncode == 0, result.stderr


def _git(path: Path, *arguments: str) -> None:
    # Static local Git executable and fixed test-generated arguments; no external input.
    subprocess.run(  # noqa: S603
        ("git", *arguments),  # noqa: S607
        cwd=path,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def local_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "source"
    repository.mkdir()
    _git(repository, "init", "--initial-branch=main")
    _git(repository, "config", "user.name", "OpsCli tests")
    _git(repository, "config", "user.email", "curupi-tests@example.invalid")
    (repository / "README.md").write_text("temporary repository\n")
    _git(repository, "add", "README.md")
    _git(repository, "commit", "-m", "initial commit")
    return repository


async def test_checkout_clones_local_repository_and_reuses_it(
    tmp_path: Path, local_repository: Path
) -> None:
    vcs = LocalGitVersionControl()
    destination = tmp_path / "workspace" / "checkout"
    request = CheckoutRequest(repo=str(local_repository), destination=destination)

    fresh = await vcs.ensure_checkout(request)
    reused = await vcs.ensure_checkout(request)

    assert fresh == Checkout(repo=str(local_repository), path=destination, cloned=True)
    assert reused == Checkout(repo=str(local_repository), path=destination, cloned=False)
    assert vcs.clone_count == 1


async def test_checkout_rejects_existing_non_git_destination(tmp_path: Path) -> None:
    destination = tmp_path / "not-a-repository"
    destination.mkdir()
    (destination / "keep.txt").write_text("preserve\n")

    with pytest.raises(WorkspacePathError, match="not a Git checkout"):
        await LocalGitVersionControl().ensure_checkout(
            CheckoutRequest(repo="local/repo", destination=destination)
        )

    assert (destination / "keep.txt").read_text() == "preserve\n"


async def test_worktree_is_created_reused_and_removed(
    tmp_path: Path, local_repository: Path
) -> None:
    vcs = LocalGitVersionControl()
    checkout = await vcs.ensure_checkout(
        CheckoutRequest(repo=str(local_repository), destination=tmp_path / "checkout")
    )

    worktree = await vcs.ensure_worktree(
        checkout, automation_id="automation", task_type="issue", task_id="42"
    )
    assert worktree.is_dir()
    assert (
        await vcs.ensure_worktree(
            checkout, automation_id="automation", task_type="issue", task_id="42"
        )
        == worktree
    )

    await vcs.remove_worktree(checkout, automation_id="automation", task_type="issue", task_id="42")
    assert not worktree.exists()
    branches = await vcs._runner.run(
        CommandRequest(
            executable="git",
            arguments=(
                "branch",
                "--list",
                f"curupi/automation/issue-{hashlib.sha256(b'42').hexdigest()}",
            ),
            cwd=checkout.path,
        )
    )
    assert branches.returncode == 0
    assert not branches.stdout.strip()


async def test_failed_setup_removes_new_clone(tmp_path: Path, local_repository: Path) -> None:
    vcs = LocalGitVersionControl()
    checkout = await vcs.ensure_checkout(
        CheckoutRequest(repo=str(local_repository), destination=tmp_path / "checkout")
    )

    class FailedSetupRunner(AsyncProcessRunner):
        @override
        async def run(
            self,
            request: CommandRequest,
            *,
            on_stdout_line: Callable[[str], Awaitable[None]] | None = None,
        ) -> ProcessResult:
            return ProcessResult(returncode=7, stderr="setup failed")

    vcs._runner = FailedSetupRunner()

    result = await vcs.run_setup_script(checkout, "setup.sh")

    assert result.returncode == 7
    assert not checkout.path.exists()
