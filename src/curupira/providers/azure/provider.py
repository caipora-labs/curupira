"""Azure DevOps pull-request task discovery and trigger behavior."""

from collections.abc import Sequence

from typing_extensions import override

from curupira.clients.az import AzClient, branch_name, organization_url
from curupira.hooks import hookimpl
from curupira.models import (
    AzPullRequest,
    AzPullRequestSearchRequest,
    AzurePullRequestAutomationConfiguration,
    ResolvedAutomation,
    Task,
    TaskIdentity,
)
from curupira.models.items import PullRequestItem
from curupira.tasks.base import FeedDependencies, TaskFeed, TaskSource, Trigger
from curupira.tasks.feed import PollingTaskFeed


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
                url=_pull_request_url(organization, project, repository, item),
                item=PullRequestItem(
                    pull_request_number=str(item.pull_request_id),
                    pull_request_title=item.title,
                    pull_request_body=item.description or "",
                    pull_request_url=_pull_request_url(organization, project, repository, item),
                    pull_request_is_draft=item.is_draft,
                    pull_request_head_ref=branch_name(item.source_ref_name),
                    pull_request_base_ref=branch_name(item.target_ref_name),
                ),
            )
            for item in items
        ]


class AzurePullRequestTrigger(Trigger):
    """Trigger implementation for Azure DevOps pull-request automations."""

    trigger_type = "azure-cli-pull-requests"
    configuration_model = AzurePullRequestAutomationConfiguration
    item_model = PullRequestItem

    @override
    def build_feed(
        self, automation: ResolvedAutomation, dependencies: FeedDependencies
    ) -> TaskFeed:
        """Build the shared polling feed backed by Azure pull-request discovery."""
        return PollingTaskFeed(
            automation,
            dependencies.polling,
            AzurePullRequestSource(AzClient(dependencies.runner)),
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


@hookimpl
def curupira_triggers() -> Sequence[Trigger]:
    """Contribute the Azure DevOps pull-request trigger."""
    return (AzurePullRequestTrigger(),)
