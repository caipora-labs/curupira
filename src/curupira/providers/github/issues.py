"""GitHub issue task discovery and trigger behavior."""

from typing_extensions import override

from curupira.clients.gh import GhClient
from curupira.models import (
    GhIssueSearchRequest,
    IssueAutomationConfiguration,
    ResolvedAutomation,
    Task,
    TaskIdentity,
)
from curupira.models.items import IssueItem
from curupira.tasks.base import FeedDependencies, TaskFeed, TaskSource, Trigger
from curupira.tasks.feed import PollingTaskFeed


class GitHubIssueSource(TaskSource):
    """Discover GitHub issue tasks through the authenticated gh client."""

    def __init__(self, gh: GhClient) -> None:
        self._gh = gh

    @override
    async def discover(self, automation: ResolvedAutomation, limit: int) -> list[Task]:
        """Search issues using the automation's existing query and result limit."""
        config = automation.configuration
        if not isinstance(config, IssueAutomationConfiguration):
            raise ValueError("GitHub issue source requires an issue configuration")
        issues = await self._gh.list_issues(
            GhIssueSearchRequest(repo=config.repo, query=config.query, limit=limit)
        )
        return [
            Task(
                identity=TaskIdentity(
                    automation_id=automation.automation_id,
                    repo=config.repo,
                    task_type="issue",
                    id=str(issue.number),
                ),
                automation=automation,
                title=issue.title,
                url=issue.url,
                item=IssueItem(
                    issue_number=str(issue.number),
                    issue_title=issue.title,
                    issue_body=issue.body or "",
                    issue_url=issue.url,
                ),
            )
            for issue in issues
        ]


class IssueTrigger(Trigger):
    """Trigger implementation for GitHub issue automations."""

    trigger_type = "issue"
    configuration_model = IssueAutomationConfiguration
    item_model = IssueItem

    @override
    def build_feed(
        self, automation: ResolvedAutomation, dependencies: FeedDependencies
    ) -> TaskFeed:
        """Build the shared polling feed backed by GitHub issue discovery."""
        return PollingTaskFeed(
            automation,
            dependencies.polling,
            GitHubIssueSource(GhClient(dependencies.runner)),
        )
