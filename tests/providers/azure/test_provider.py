"""Azure DevOps pull-request task source and trigger behavior."""

from pathlib import Path

import pytest
from typing_extensions import override

from curupira.clients.az import AzClient
from curupira.models import (
    AzPullRequest,
    AzPullRequestSearchRequest,
    PollingSettings,
    Task,
    TaskIdentity,
)
from curupira.models.items import PullRequestItem
from curupira.providers.azure import AzurePullRequestSource, AzurePullRequestTrigger
from curupira.storage import CronScheduleRepository
from curupira.tasks.base import FeedDependencies
from curupira.tasks.feed import PollingTaskFeed
from curupira.tasks.registry import get
from tests.helpers import resolved_automation


class FakeAzClient(AzClient):
    """Return controlled pull requests and retain the search request."""

    def __init__(self, pull_requests: list[AzPullRequest]) -> None:
        super().__init__()
        self.pull_requests = pull_requests
        self.request: AzPullRequestSearchRequest | None = None

    @override
    async def list_pull_requests(self, request: AzPullRequestSearchRequest) -> list[AzPullRequest]:
        self.request = request
        return self.pull_requests


@pytest.mark.asyncio
async def test_source_lists_pull_requests_and_builds_tasks(tmp_path: Path) -> None:
    az = FakeAzClient(
        [
            AzPullRequest(
                pullRequestId=42,
                title="Review change",
                description="Details",
                isDraft=True,
                sourceRefName="refs/heads/feature",
                targetRefName="refs/heads/main",
                _links={
                    "web": {
                        "href": "https://dev.azure.com/contoso/api-project/_git/api/pullrequest/42"
                    }
                },
            )
        ]
    )
    automation = resolved_automation(
        tmp_path,
        "azure-reviews",
        "azure-cli-pull-requests",
        status="active",
        source_branch="feature",
        target_branch="main",
    )

    tasks = await AzurePullRequestSource(az).discover(automation, 7)

    assert az.request == AzPullRequestSearchRequest(
        organization="contoso",
        project="api-project",
        repository="api",
        limit=7,
        status="active",
        source_branch="feature",
        target_branch="main",
    )
    assert len(tasks) == 1
    assert tasks[0].identity.id == "42"
    assert tasks[0].identity.task_type == "azure-cli-pull-requests"
    assert tasks[0].identity.repo == "contoso/api-project/api"
    assert tasks[0].title == "Review change"
    assert tasks[0].url == ("https://dev.azure.com/contoso/api-project/_git/api/pullrequest/42")
    assert tasks[0].item == PullRequestItem(
        pull_request_number="42",
        pull_request_title="Review change",
        pull_request_body="Details",
        pull_request_url="https://dev.azure.com/contoso/api-project/_git/api/pullrequest/42",
        pull_request_is_draft=True,
        pull_request_head_ref="feature",
        pull_request_base_ref="main",
    )


@pytest.mark.asyncio
async def test_source_constructs_web_url_when_links_are_absent(tmp_path: Path) -> None:
    az = FakeAzClient(
        [
            AzPullRequest(
                pullRequestId=7,
                title="No links",
                description=None,
            )
        ]
    )
    automation = resolved_automation(tmp_path, "azure-reviews", "azure-cli-pull-requests")

    tasks = await AzurePullRequestSource(az).discover(automation, 1)

    assert tasks[0].url == ("https://dev.azure.com/contoso/api-project/_git/api/pullrequest/7")


def test_azure_pull_request_trigger_is_registered_and_provides_prompt_context(
    tmp_path: Path,
) -> None:
    trigger = get("azure-cli-pull-requests")
    assert trigger.trigger_type == "azure-cli-pull-requests"
    automation = resolved_automation(tmp_path, "azure-reviews", "azure-cli-pull-requests")
    task = Task(
        identity=TaskIdentity(
            automation_id="azure-reviews",
            repo="contoso/api-project/api",
            task_type="azure-cli-pull-requests",
            id="54",
        ),
        automation=automation,
        title="Review",
        url="https://dev.azure.com/contoso/api-project/_git/api/pullrequest/54",
        item=PullRequestItem(
            pull_request_number="54",
            pull_request_title="Review",
            pull_request_url="https://dev.azure.com/contoso/api-project/_git/api/pullrequest/54",
            pull_request_is_draft=True,
            pull_request_head_ref="feature",
            pull_request_base_ref="main",
        ),
    )

    assert isinstance(trigger, AzurePullRequestTrigger)
    assert trigger.prompt_fields() == frozenset(
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
    assert trigger.prompt_context(task) == {
        "pull_request_number": "54",
        "pull_request_title": "Review",
        "pull_request_body": "",
        "pull_request_url": "https://dev.azure.com/contoso/api-project/_git/api/pullrequest/54",
        "pull_request_is_draft": "true",
        "pull_request_head_ref": "feature",
        "pull_request_base_ref": "main",
    }


def test_azure_pull_request_trigger_builds_polling_feed(tmp_path: Path) -> None:
    automation = resolved_automation(tmp_path, "azure-reviews", "azure-cli-pull-requests")

    feed = AzurePullRequestTrigger().build_feed(
        automation,
        FeedDependencies(
            polling=PollingSettings(),
            cron=CronScheduleRepository(tmp_path / "state.sqlite3"),
            state_db_path=tmp_path / "state.sqlite3",
        ),
    )

    assert isinstance(feed, PollingTaskFeed)
    assert feed.automation is automation
