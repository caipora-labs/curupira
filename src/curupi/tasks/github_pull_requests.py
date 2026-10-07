"""GitHub pull-request task discovery and trigger behavior."""

from typing_extensions import override

from curupi.clients.gh import GhClient
from curupi.models import (
    GhPullRequestSearchRequest,
    PullRequestAutomationConfiguration,
    ResolvedAutomation,
    Task,
    TaskIdentity,
)
from curupi.tasks.base import FeedDependencies, TaskFeed, TaskSource, Trigger
from curupi.tasks.feed import PollingTaskFeed
from curupi.tasks.registry import register, register_alias


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
            GhPullRequestSearchRequest(repo=config.repo, query=config.query, limit=limit)
        )
        return [
            Task(
                identity=TaskIdentity(
                    automation_id=automation.automation_id,
                    repo=config.repo,
                    task_type="pull_request",
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


class PullRequestTrigger(Trigger):
    """Trigger implementation for GitHub pull-request automations."""

    trigger_type = "github-cli-pull-requests"

    @classmethod
    @override
    def prompt_fields(cls) -> frozenset[str]:
        """Return the pull-request-specific prompt placeholders."""
        return frozenset(
            {
                "pull_request_number",
                "pull_request_title",
                "pull_request_body",
                "pull_request_url",
                "pull_request_is_draft",
                "pull_request_head_ref",
                "pull_request_base_ref",
            }
        )

    @override
    def prompt_context(self, task: Task) -> dict[str, str]:
        """Map a pull request into its pull-request-specific placeholders."""
        return {
            "pull_request_number": task.identity.id,
            "pull_request_title": task.title,
            "pull_request_body": task.body or "",
            "pull_request_url": task.url,
            "pull_request_is_draft": (
                str(task.is_draft).lower() if task.is_draft is not None else ""
            ),
            "pull_request_head_ref": task.head_ref_name or "",
            "pull_request_base_ref": task.base_ref_name or "",
        }

    @override
    def build_feed(
        self, automation: ResolvedAutomation, dependencies: FeedDependencies
    ) -> TaskFeed:
        """Build the shared polling feed backed by pull-request discovery."""
        return PollingTaskFeed(
            automation, dependencies.polling, GitHubPullRequestSource(dependencies.gh)
        )


register(PullRequestTrigger())
register_alias("github-cli-pull-requests", "pull_request")
