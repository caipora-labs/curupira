"""Azure DevOps pull-request task discovery and trigger behavior."""

from typing_extensions import override

from curupira.clients.az import AzClient, branch_name, organization_url
from curupira.models import (
    AzPullRequest,
    AzPullRequestSearchRequest,
    AzurePullRequestAutomationConfiguration,
    ResolvedAutomation,
    Task,
    TaskIdentity,
)
from curupira.tasks.base import FeedDependencies, TaskFeed, TaskSource, Trigger
from curupira.tasks.feed import PollingTaskFeed
from curupira.tasks.registry import register


class AzurePullRequestSource(TaskSource):
    """Discover pull-request tasks through the authenticated Azure CLI."""

    def __init__(self, az: AzClient) -> None:
        self._az = az

    @override
    async def discover(self, automation: ResolvedAutomation, limit: int) -> list[Task]:
        """List pull requests using the automation's Azure DevOps repository."""
        config = automation.configuration
        if not isinstance(config, AzurePullRequestAutomationConfiguration):
            raise ValueError(
                "Azure pull-request source requires an Azure pull-request configuration"
            )
        organization, project, repository = config.repo.split("/", 2)
        items = await self._az.list_pull_requests(
            AzPullRequestSearchRequest(
                organization=organization,
                project=project,
                repository=repository,
                limit=limit,
                status=config.status,
                source_branch=config.source_branch,
                target_branch=config.target_branch,
            )
        )
        return [
            Task(
                identity=TaskIdentity(
                    automation_id=automation.automation_id,
                    repo=config.repo,
                    task_type="azure-cli-pull-requests",
                    id=str(item.pull_request_id),
                ),
                automation=automation,
                title=item.title,
                body=item.description,
                url=_pull_request_url(organization, project, repository, item),
                is_draft=item.is_draft,
                head_ref_name=branch_name(item.source_ref_name),
                base_ref_name=branch_name(item.target_ref_name),
            )
            for item in items
        ]


class AzurePullRequestTrigger(Trigger):
    """Trigger implementation for Azure DevOps pull-request automations."""

    trigger_type = "azure-cli-pull-requests"

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
        """Build the shared polling feed backed by Azure pull-request discovery."""
        return PollingTaskFeed(
            automation, dependencies.polling, AzurePullRequestSource(dependencies.az)
        )


def _pull_request_url(
    organization: str,
    project: str,
    repository: str,
    item: AzPullRequest,
) -> str:
    if (web_url := item.web_url()) is not None:
        return web_url
    return (
        f"{organization_url(organization)}/{project}/_git/{repository}"
        f"/pullrequest/{item.pull_request_id}"
    )


register(AzurePullRequestTrigger())
