"""GitHub pull-request task discovery and trigger behavior."""

from typing_extensions import override

from curupira.clients.gh import GhClient
from curupira.models import (
    GhPullRequestSearchRequest,
    PullRequestAutomationConfiguration,
    ResolvedAutomation,
    Task,
    TaskIdentity,
)
from curupira.models.items import PullRequestItem
from curupira.tasks.base import FeedDependencies, TaskFeed, TaskSource, Trigger
from curupira.tasks.feed import PollingTaskFeed
from curupira.tasks.registry import register


class GitHubPullRequestSource(TaskSource):
    """Discover pull-request tasks through the authenticated gh client."""

    def __init__(self, gh: GhClient) -> None:
        self._gh = gh

    @override
    async def discover(self, automation: ResolvedAutomation, limit: int) -> list[Task]:
        """Search pull requests using the automation's query and result limit."""
        config = automation.configuration
        if not isinstance(config, PullRequestAutomationConfiguration):
            raise ValueError("GitHub pull-request source requires a pull-request configuration")
        items = await self._gh.list_pull_requests(
            GhPullRequestSearchRequest(
                repo=config.repo, query=config.query, limit=limit, jq=config.jq
            )
        )
        return [
            Task(
                identity=TaskIdentity(
                    automation_id=automation.automation_id,
                    repo=config.repo,
                    task_type="github-cli-pull-requests",
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

    trigger_type = "github-cli-pull-requests"
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
            GitHubPullRequestSource(GhClient(dependencies.runner)),
        )


register(PullRequestTrigger())
