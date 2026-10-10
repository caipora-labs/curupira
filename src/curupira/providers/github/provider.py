"""GitHub provider: issue and pull-request triggers."""

from collections.abc import Sequence

from curupira.hooks import hookimpl
from curupira.providers.github.issues import IssueTrigger
from curupira.providers.github.pull_requests import PullRequestTrigger
from curupira.tasks.base import Trigger


@hookimpl
def curupira_triggers() -> Sequence[Trigger]:
    """Contribute GitHub issue and pull-request triggers."""
    return (IssueTrigger(), PullRequestTrigger())
