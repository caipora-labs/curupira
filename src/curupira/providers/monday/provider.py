"""monday.com board item task discovery and trigger behavior."""

from collections.abc import Sequence

from typing_extensions import override

from curupira.clients.monday import MondayClient
from curupira.hooks import hookimpl
from curupira.models import (
    MondayAutomationConfiguration,
    ResolvedAutomation,
    Task,
    TaskIdentity,
)
from curupira.models.items import MondayItem
from curupira.models.monday import MondayBoardItem, MondayColumnValue, MondayListRequest
from curupira.tasks.base import FeedDependencies, TaskFeed, TaskSource, Trigger
from curupira.tasks.feed import PollingTaskFeed

_MAX_PAGE_SIZE = 500
_INACTIVE_STATES = frozenset({"archived", "deleted"})


class MondayItemSource(TaskSource):
    """Discover monday.com board items through the GraphQL API."""

    def __init__(self, client: MondayClient) -> None:
        self._client = client
        self._cursor: str | None = None

    @override
    async def discover(self, automation: ResolvedAutomation, limit: int) -> list[Task]:
        """Fetch up to ``limit`` active items, resuming from the preserved page cursor."""
        config = automation.configuration
        if not isinstance(config, MondayAutomationConfiguration):
            raise ValueError("monday.com source requires a monday-items configuration")
        if limit < 1:
            return []

        tasks: list[Task] = []
        seen_ids: set[str] = set()
        seen_cursors: set[str] = set()
        cursor = self._cursor
        while len(tasks) < limit:
            page_limit = min(limit - len(tasks), _MAX_PAGE_SIZE)
            page = await self._client.list_items_page(
                MondayListRequest(
                    board_id=config.board_id,
                    group_ids=config.group_ids,
                    cursor=cursor,
                    limit=page_limit,
                )
            )
            if not page.cursor or page.cursor == cursor or page.cursor in seen_cursors:
                self._cursor = None
            else:
                self._cursor = page.cursor
                seen_cursors.add(page.cursor)
            for item in page.items:
                if item.id in seen_ids:
                    continue
                seen_ids.add(item.id)
                if _is_inactive(item):
                    continue
                tasks.append(_task_from_item(automation, config, item))
                if len(tasks) >= limit:
                    return tasks
            if not self._cursor:
                break
            cursor = self._cursor
        return tasks


class MondayItemTrigger(Trigger):
    """Trigger implementation for monday.com board item automations."""

    trigger_type = "monday-items"
    configuration_model = MondayAutomationConfiguration
    item_model = MondayItem

    @override
    def build_feed(
        self, automation: ResolvedAutomation, dependencies: FeedDependencies
    ) -> TaskFeed:
        """Build the shared polling feed backed by the monday.com GraphQL client."""
        config = automation.configuration
        if not isinstance(config, MondayAutomationConfiguration):
            raise ValueError("monday.com trigger requires a monday-items configuration")
        return PollingTaskFeed(
            automation,
            dependencies.polling,
            MondayItemSource(MondayClient(token_env=config.token_env)),
        )


@hookimpl
def curupira_triggers() -> Sequence[Trigger]:
    """Contribute the monday.com board item trigger."""
    return (MondayItemTrigger(),)


def _is_inactive(item: MondayBoardItem) -> bool:
    """Return whether the item is archived or deleted."""
    return item.state.lower() in _INACTIVE_STATES


def _task_from_item(
    automation: ResolvedAutomation,
    config: MondayAutomationConfiguration,
    item: MondayBoardItem,
) -> Task:
    """Map one API item into a Curupira task with string-preserved identity."""
    group_id = item.group.id if item.group is not None else ""
    group_title = item.group.title if item.group is not None else ""
    return Task(
        identity=TaskIdentity(
            automation_id=automation.automation_id,
            repo=automation.identity_repo,
            task_type=config.trigger_type,
            id=item.id,
        ),
        automation=automation,
        title=item.name,
        url=item.url,
        item=MondayItem(
            item_id=item.id,
            item_name=item.name,
            item_url=item.url,
            item_group_id=group_id,
            item_group_title=group_title,
            board_id=config.board_id,
            item_state=item.state,
            item_columns=_format_columns(item.column_values),
        ),
    )


def _format_columns(columns: tuple[MondayColumnValue, ...]) -> str:
    """Render column values as plain text for prompt placeholders."""
    lines: list[str] = []
    for column in columns:
        text = (column.text or "").strip()
        if not text:
            continue
        lines.append(f"{column.id}: {text}")
    return "\n".join(lines)
