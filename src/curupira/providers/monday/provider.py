"""monday.com board item task discovery and trigger behavior."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from typing_extensions import override

from curupira.clients.monday import MondayClient
from curupira.errors import HttpApiError, TransientHttpApiError
from curupira.hooks import hookimpl
from curupira.models import (
    MondayAutomationConfiguration,
    ResolvedAutomation,
    Task,
    TaskIdentity,
)
from curupira.models.items import MondayItem
from curupira.models.monday import (
    MondayBoardItem,
    MondayColumnValue,
    MondayItemsPage,
    MondayListRequest,
)
from curupira.tasks.base import FeedDependencies, TaskFeed, TaskSource, Trigger
from curupira.tasks.feed import PollingTaskFeed

_MAX_PAGE_SIZE = 500
_INACTIVE_STATES = frozenset({"archived", "deleted"})


@dataclass(frozen=True)
class _PageFetchResult:
    """Outcome of one monday.com page request during discovery."""

    kind: Literal["page", "reset_cursor", "return_partial"]
    page: MondayItemsPage | None = None


class MondayItemSource(TaskSource):
    """Discover monday.com board items through the GraphQL API."""

    def __init__(self, client: MondayClient) -> None:
        self._client = client
        self._cursor: str | None = None

    @override
    async def discover(self, automation: ResolvedAutomation, limit: int) -> list[Task]:
        """Fetch up to ``limit`` active items, resuming from the preserved page cursor.

        The page cursor is confirmed only after a page is successfully integrated. When a
        later page fails after some tasks were already collected, those tasks are returned
        and the cursor stays at the next unread page. A non-transient failure while using a
        stored cursor clears it and retries the first page once (cursors expire after about
        60 minutes).
        """
        config = automation.configuration
        if not isinstance(config, MondayAutomationConfiguration):
            raise ValueError("monday.com source requires a monday-items configuration")
        if limit < 1:
            return []

        tasks: list[Task] = []
        seen_ids: set[str] = set()
        seen_cursors: set[str] = set()
        cursor = self._cursor
        cursor_reset_attempted = False
        while len(tasks) < limit:
            result = await self._fetch_page(
                config,
                cursor=cursor,
                page_limit=min(limit - len(tasks), _MAX_PAGE_SIZE),
                tasks=tasks,
                cursor_reset_attempted=cursor_reset_attempted,
            )
            if result.kind == "reset_cursor":
                self._cursor = None
                cursor = None
                cursor_reset_attempted = True
                continue
            if result.kind == "return_partial" or result.page is None:
                return tasks

            page = result.page
            pending_cursor = _pending_cursor(page.cursor, cursor, seen_cursors)
            _append_active_items(tasks, seen_ids, automation, config, page.items)
            self._cursor = pending_cursor
            if len(tasks) >= limit or not self._cursor:
                return tasks[:limit]
            cursor = self._cursor
        return tasks

    async def _fetch_page(
        self,
        config: MondayAutomationConfiguration,
        *,
        cursor: str | None,
        page_limit: int,
        tasks: list[Task],
        cursor_reset_attempted: bool,
    ) -> _PageFetchResult:
        """Load one page, or signal a cursor reset / partial return."""
        try:
            page = await self._client.list_items_page(
                MondayListRequest(
                    board_id=config.board_id,
                    group_ids=config.group_ids,
                    cursor=cursor,
                    limit=page_limit,
                )
            )
        except TransientHttpApiError:
            if tasks:
                return _PageFetchResult(kind="return_partial")
            raise
        except HttpApiError:
            if cursor is not None and not cursor_reset_attempted:
                return _PageFetchResult(kind="reset_cursor")
            if tasks:
                return _PageFetchResult(kind="return_partial")
            raise
        return _PageFetchResult(kind="page", page=page)


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


def _pending_cursor(
    page_cursor: str | None,
    current: str | None,
    seen_cursors: set[str],
) -> str | None:
    """Return the next cursor to store, or ``None`` when pagination is finished."""
    if not page_cursor or page_cursor == current or page_cursor in seen_cursors:
        return None
    seen_cursors.add(page_cursor)
    return page_cursor


def _append_active_items(
    tasks: list[Task],
    seen_ids: set[str],
    automation: ResolvedAutomation,
    config: MondayAutomationConfiguration,
    items: tuple[MondayBoardItem, ...],
) -> None:
    """Append active, unseen items from one page onto ``tasks``."""
    for item in items:
        if item.id in seen_ids:
            continue
        seen_ids.add(item.id)
        if _is_inactive(item):
            continue
        tasks.append(_task_from_item(automation, config, item))


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
