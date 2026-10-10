"""Task discovery contracts and compatibility re-exports of built-in triggers.

Built-in triggers register through Pluggy provider packages under ``curupira.providers``.
Import paths under ``curupira.tasks.<name>`` remain available for compatibility.
"""

from curupira.tasks import (  # noqa: F401
    azure_pull_requests,
    cron,
    github_issues,
    github_pull_requests,
    trello_cards,
)
