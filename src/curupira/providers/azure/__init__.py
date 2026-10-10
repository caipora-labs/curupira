"""Azure DevOps task-source provider."""

from curupira.providers.azure.provider import AzurePullRequestSource, AzurePullRequestTrigger

__all__ = [
    "AzurePullRequestSource",
    "AzurePullRequestTrigger",
]
