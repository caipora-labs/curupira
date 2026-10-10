"""Compatibility re-export of the GitHub issues trigger."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from curupira.providers.github.issues import GitHubIssueSource as GitHubIssueSource
    from curupira.providers.github.issues import IssueTrigger as IssueTrigger


def __getattr__(name: str) -> object:
    """Load the GitHub issues provider lazily to avoid import cycles."""
    if name in {"GitHubIssueSource", "IssueTrigger"}:
        from curupira.providers.github import issues as module

        return getattr(module, name)
    raise AttributeError(name)
