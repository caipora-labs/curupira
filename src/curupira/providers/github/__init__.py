"""GitHub task-source provider (issues and pull requests)."""

from curupira.providers.github.issues import GitHubIssueSource, IssueTrigger
from curupira.providers.github.pull_requests import (
    GitHubPullRequestSource,
    PullRequestTrigger,
)

__all__ = [
    "GitHubIssueSource",
    "GitHubPullRequestSource",
    "IssueTrigger",
    "PullRequestTrigger",
]
