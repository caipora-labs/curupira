"""GitHub issue task discovery and trigger behavior."""

from typing_extensions import override

from curupira.clients.github_graphql import GitHubGraphQLClient
from curupira.clients.github_search import build_github_search_query
from curupira.models import (
    GitHubSearchRequest,
    IssueAutomationConfiguration,
    ResolvedAutomation,
    Task,
    TaskIdentity,
)
from curupira.models.items import IssueItem
from curupira.tasks.base import FeedDependencies, TaskFeed, TaskSource, Trigger
from curupira.tasks.feed import PollingTaskFeed


class GitHubIssueSource(TaskSource):
    """Discover GitHub issue tasks through the GraphQL Search API."""

    def __init__(self, client: GitHubGraphQLClient) -> None:
        self._client = client

    @override
    async def discover(self, automation: ResolvedAutomation, limit: int) -> list[Task]:
        """Search issues using the automation's typed filters and result limit."""
        config = automation.configuration
        if not isinstance(config, IssueAutomationConfiguration):
            raise ValueError("GitHub issue source requires an issue configuration")
        query = build_github_search_query(config, item_kind="issue")
        issues = await self._client.list_issues(
            GitHubSearchRequest(
                repo=config.repo,
                query=query,
                limit=limit,
                item_kind="issue",
            ),
            configuration=config,
        )
        return [
            Task(
                identity=TaskIdentity(
                    automation_id=automation.automation_id,
                    repo=automation.identity_repo,
                    task_type="github-issues",
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

    trigger_type = "github-issues"
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
            GitHubIssueSource(GitHubGraphQLClient(dependencies.runner)),
        )
