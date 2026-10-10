"""Compatibility re-export of the GitHub pull-request trigger."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from curupira.providers.github.pull_requests import (
        GitHubPullRequestSource as GitHubPullRequestSource,
    )
    from curupira.providers.github.pull_requests import PullRequestTrigger as PullRequestTrigger


def __getattr__(name: str) -> object:
    """Load the GitHub pull-request provider lazily to avoid import cycles."""
    if name in {"GitHubPullRequestSource", "PullRequestTrigger"}:
        from curupira.providers.github import pull_requests as module

        return getattr(module, name)
    raise AttributeError(name)
