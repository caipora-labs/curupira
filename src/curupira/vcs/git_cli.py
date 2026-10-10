"""Native Git CLI-backed repository cloning."""

from pathlib import Path

from typing_extensions import override

from curupira.errors import CliExecutionError
from curupira.models import CommandRequest
from curupira.vcs.base import VersionControl


class NativeGitVersionControl(VersionControl):
    """Clone repositories through ``git clone`` using the configured remote URL."""

    @override
    async def clone(self, remote: str, destination: Path) -> None:
        """Run ``git clone <remote> <destination>`` without managing authentication."""
        result = await self._runner.run(
            CommandRequest(
                executable="git",
                arguments=("clone", remote, str(destination)),
            )
        )
        if result.returncode:
            raise CliExecutionError("git", result.returncode, result.stderr)
