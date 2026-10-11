"""Compatibility re-export of the Azure DevOps pull-request trigger."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from curupira.providers.azure.provider import (
        AzurePullRequestSource as AzurePullRequestSource,
    )
    from curupira.providers.azure.provider import (
        AzurePullRequestTrigger as AzurePullRequestTrigger,
    )


def __getattr__(name: str) -> object:
    """Load the Azure pull-request provider lazily to avoid import cycles."""
    if name in {"AzurePullRequestSource", "AzurePullRequestTrigger"}:
        from curupira.providers.azure import provider as module

        return getattr(module, name)
    raise AttributeError(name)
