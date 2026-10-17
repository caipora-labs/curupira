"""Official GitHub issues / pull-requests trigger extension."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field

from curupira_official import __version__
from curupira_sdk import Curupira, RpcError

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

app = Curupira(name="curupira-github", version=__version__)


@dataclass
class Issue:
    number: int
    title: str
    url: str
    body: str = ""
    labels: list[str] = field(default_factory=list)
    author: str = ""
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(self.number)


@dataclass
class PullRequest:
    number: int
    title: str
    url: str
    body: str = ""
    labels: list[str] = field(default_factory=list)
    author: str = ""
    head_ref: str = ""
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(self.number)


def _validate_repo(repo: str) -> None:
    if _REPO_RE.fullmatch(repo) is None:
        raise RpcError(-32003, "repo must use the owner/repository format")
    if any(part in {".", ".."} for part in repo.split("/")):
        raise RpcError(-32003, "repo must not contain traversal segments")


def _check_repo(kwargs: dict[str, object]) -> None:
    repo = kwargs.get("repo")
    if not isinstance(repo, str):
        raise RpcError(-32003, "repo must use the owner/repository format")
    _validate_repo(repo)


@app.trigger
async def github_issues(
    repo: str,
    labels: list[str] | None = None,
    exclude_labels: list[str] | None = None,
    state: str = "open",
    linked_pull_request: bool | None = None,
    sort: str | None = None,
) -> Issue | None:
    """Return the next eligible GitHub issue, or None when none are available."""
    del repo, labels, exclude_labels, state, linked_pull_request, sort
    return None


@app.trigger
async def github_pull_requests(
    repo: str,
    labels: list[str] | None = None,
    draft: bool | None = None,
    mergeable: bool | None = None,
    ci_status: str | None = None,
    sort: str | None = None,
) -> PullRequest | None:
    """Return the next eligible GitHub pull request, or None when none are available."""
    del repo, labels, draft, mergeable, ci_status, sort
    return None


app.param_check("github_issues", _check_repo)
app.param_check("github_pull_requests", _check_repo)


MANIFEST = """
manifest_version = 1
name = "curupira-github"
version = "{version}"
protocol_version = 1
runtime = "python"
kind = "trigger"
trigger_types = ["github_issues", "github_pull_requests"]

[launch]
type = "executable"
program = "{python}"
args = ["-m", "curupira_official.github_ext"]
""".strip()


def main() -> None:
    if "--curupira-print-manifest" in sys.argv:
        app.print_manifest(MANIFEST)
        return
    app.run()


if __name__ == "__main__":
    main()
