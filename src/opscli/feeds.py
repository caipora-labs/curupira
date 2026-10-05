"""Shared GitHub polling and persistent cron task discovery."""

from opscli.clients.gh import GhClient
from opscli.models import (
    CronAutomationConfiguration,
    GhPullRequest,
    GhPullRequestSearchRequest,
    ResolvedAutomation,
    Task,
    TaskIdentity,
)
from opscli.tasks.base import TaskSource


class GitHubTaskSource(TaskSource):
    """Discover pull-request tasks through the GitHub client contract."""

    def __init__(self, gh: GhClient) -> None:
        self._gh = gh

    async def discover(self, automation: ResolvedAutomation, limit: int) -> list[Task]:
        """Query the configured GitHub item type and construct automation tasks."""
        config = automation.configuration
        if isinstance(config, CronAutomationConfiguration):
            raise ValueError("GitHub source cannot consume a cron configuration")
        if config.trigger_type != "pull_request":
            raise ValueError("GitHub task source requires a pull-request configuration")
        items = await self._gh.list_pull_requests(
            GhPullRequestSearchRequest(repo=config.repo, query=config.query, limit=limit)
        )
        return [
            Task(
                identity=TaskIdentity(
                    automation_id=automation.automation_id,
                    repo=config.repo,
                    task_type=config.trigger_type,
                    id=str(item.number),
                ),
                automation=automation,
                title=item.title,
                body=item.body,
                url=item.url,
                is_draft=item.is_draft,
                head_ref_name=item.head_ref_name,
                base_ref_name=item.base_ref_name,
            )
            for item in items
        ]
