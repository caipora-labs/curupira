"""Task sources and trigger implementations."""

# Import concrete triggers so registry lookups work regardless of which application
# entry point is used first.
from curupira.tasks import cron, github_issues, github_pull_requests  # noqa: F401
