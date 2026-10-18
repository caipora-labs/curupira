"""Official Azure DevOps pull-request trigger."""

from __future__ import annotations

import re
from dataclasses import dataclass

from curupira_sdk import Curupira, RpcError

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


@dataclass
class AzurePullRequest:
    pull_request_number: int
    pull_request_title: str
    pull_request_url: str
    pull_request_body: str = ""
    pull_request_head_ref: str = ""
    pull_request_base_ref: str = ""


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


def register(app: Curupira) -> None:
    """Register Azure DevOps triggers on ``app``."""

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

    app.param_check("azure-cli-pull-requests", _check_repo)
