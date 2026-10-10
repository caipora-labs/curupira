"""GitHub pull-request task discovery and trigger behavior."""

from typing_extensions import override

from curupira.clients.github_graphql import GitHubGraphQLClient
from curupira.clients.github_search import build_github_search_query
from curupira.models import (
    GitHubSearchRequest,
    PullRequestAutomationConfiguration,
    ResolvedAutomation,
    Task,
    TaskIdentity,
)
from curupira.models.items import PullRequestItem
from curupira.tasks.base import FeedDependencies, TaskFeed, TaskSource, Trigger
from curupira.tasks.feed import PollingTaskFeed


class GitHubPullRequestSource(TaskSource):
    """Discover pull-request tasks through the GraphQL Search API."""

    def __init__(self, client: GitHubGraphQLClient) -> None:
        self._client = client

    @override
    async def discover(self, automation: ResolvedAutomation, limit: int) -> list[Task]:
        """Search pull requests using the automation's typed filters and result limit."""
        config = automation.configuration
        if not isinstance(config, PullRequestAutomationConfiguration):
            raise ValueError("GitHub pull-request source requires a pull-request configuration")
        query = build_github_search_query(config, item_kind="pull_request")
        items = await self._client.list_pull_requests(
            GitHubSearchRequest(
                repo=config.repo,
                query=query,
                limit=limit,
                item_kind="pull_request",
            ),
            configuration=config,
        )
        return [
            Task(
                identity=TaskIdentity(
                    automation_id=automation.automation_id,
                    repo=automation.identity_repo,
                    task_type="github-pull-requests",
                    id=str(item.number),
                ),
                automation=automation,
                title=item.title,
                url=item.url,
                item=PullRequestItem(
                    pull_request_number=str(item.number),
                    pull_request_title=item.title,
                    pull_request_body=item.body or "",
                    pull_request_url=item.url,
                    pull_request_is_draft=item.is_draft,
                    pull_request_head_ref=item.head_ref_name,
                    pull_request_base_ref=item.base_ref_name,
                ),
            )
            for item in items
        ]


class PullRequestTrigger(Trigger):
    """Trigger implementation for GitHub pull-request automations."""

    trigger_type = "github-pull-requests"
    configuration_model = PullRequestAutomationConfiguration
    item_model = PullRequestItem

    @override
    def build_feed(
        self, automation: ResolvedAutomation, dependencies: FeedDependencies
    ) -> TaskFeed:
        """Build the shared polling feed backed by pull-request discovery."""
        return PollingTaskFeed(
            automation,
            dependencies.polling,
            GitHubPullRequestSource(GitHubGraphQLClient(dependencies.runner)),
        )
