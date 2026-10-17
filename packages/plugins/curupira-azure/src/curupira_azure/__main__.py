"""Official Azure DevOps pull-request trigger extension."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass

from curupira_sdk import Curupira, RpcError

from curupira_azure import __version__

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

app = Curupira(name="curupira-azure", version=__version__)


@dataclass
class AzurePullRequest:
    pull_request_number: int
    pull_request_title: str
    pull_request_url: str
    pull_request_body: str = ""
    pull_request_head_ref: str = ""
    pull_request_base_ref: str = ""
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(self.pull_request_number)


def _validate_repo(repo: str) -> None:
    if _REPO_RE.fullmatch(repo) is None:
        raise RpcError(-32003, "repo must use the organization/project/repository format")
    if any(part in {".", ".."} for part in repo.split("/")):
        raise RpcError(-32003, "repo must not contain traversal segments")


def _check_repo(kwargs: dict[str, object]) -> None:
    repo = kwargs.get("repo")
    if not isinstance(repo, str):
        raise RpcError(-32003, "repo must use the organization/project/repository format")
    _validate_repo(repo)


@app.trigger
def azure_cli_pull_requests(
    repo: str,
    status: str | None = None,
    source_branch: str | None = None,
    target_branch: str | None = None,
) -> AzurePullRequest | None:
    """Return the next eligible Azure DevOps pull request, or None."""
    del repo, status, source_branch, target_branch
    return None


app.param_check("azure_cli_pull_requests", _check_repo)


MANIFEST = """
manifest_version = 1
name = "curupira-azure"
version = "{version}"
protocol_version = 1
runtime = "python"
kind = "trigger"
trigger_types = ["azure_cli_pull_requests"]

[launch]
type = "executable"
program = "{python}"
args = ["-m", "curupira_azure"]
""".strip()


def main() -> None:
    if "--curupira-print-manifest" in sys.argv:
        app.print_manifest(MANIFEST)
        return
    app.run()


if __name__ == "__main__":
    main()
