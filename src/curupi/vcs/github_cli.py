"""GitHub CLI-backed repository cloning."""

from pathlib import Path

from curupi.errors import CliExecutionError
from curupi.models import CommandRequest
from curupi.vcs.base import VersionControl


class GitHubCliVersionControl(VersionControl):
    """Clone GitHub repositories through the user's existing ``gh`` login."""

    async def clone(self, repo: str, destination: Path) -> None:
        """Run ``gh repo clone`` without managing authentication."""
        result = await self._runner.run(
            CommandRequest(executable="gh", arguments=("repo", "clone", repo, str(destination)))
        )
        if result.returncode:
            raise CliExecutionError("gh", result.returncode, result.stderr)
