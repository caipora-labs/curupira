"""monday.com item source and trigger behavior."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import pytest
from typing_extensions import override

from curupira.clients.monday import MondayClient
from curupira.models import MondayListRequest, PollingSettings, Task, TaskIdentity
from curupira.models.items import MondayItem
from curupira.models.monday import MondayBoardItem, MondayColumnValue, MondayGroup, MondayItemsPage
from curupira.providers.monday import MondayItemSource, MondayItemTrigger
from curupira.storage import CronScheduleRepository
from curupira.tasks.base import FeedDependencies
from curupira.tasks.feed import PollingTaskFeed
from curupira.tasks.registry import get
from tests.helpers import resolved_automation

_TOKEN = "monday-test-token"


class FakeMondayClient(MondayClient):
    """Return scripted pages and record list requests."""

    def __init__(self, pages: list[MondayItemsPage]) -> None:
        super().__init__(environ={"MONDAY_API_TOKEN": _TOKEN})
        self._pages = list(pages)
        self.requests: list[MondayListRequest] = []

    @override
    async def list_items_page(self, request: MondayListRequest) -> MondayItemsPage:
        self.requests.append(request)
        if not self._pages:
            return MondayItemsPage(items=(), cursor=None)
        return self._pages.pop(0)


def _board_item(
    item_id: str,
    name: str,
    *,
    state: str = "active",
    group_id: str = "topics",
    group_title: str = "Topics",
) -> MondayBoardItem:
    return MondayBoardItem(
        id=item_id,
        name=name,
        url=f"https://acme.monday.com/boards/1234567890/pulses/{item_id}",
        state=state,
        group=MondayGroup(id=group_id, title=group_title),
        column_values=(MondayColumnValue(id="status", text="Working on it"),),
    )


@pytest.mark.asyncio
async def test_source_maps_items_and_skips_archived(tmp_path: Path) -> None:
    client = FakeMondayClient(
        [
            MondayItemsPage(
                items=(
                    _board_item("111", "Active work"),
                    _board_item("222", "Old", state="archived"),
                    _board_item("333", "Gone", state="deleted"),
                ),
                cursor=None,
            )
        ]
    )
    automation = resolved_automation(
        tmp_path,
        "board-items",
        "monday-items",
        board_id="1234567890",
        group_ids=("topics",),
    )

    tasks = await MondayItemSource(client).discover(automation, 8)

    assert client.requests == [
        MondayListRequest(
            board_id="1234567890",
            group_ids=("topics",),
            cursor=None,
            limit=8,
        )
    ]
    assert len(tasks) == 1
    assert tasks[0].identity.id == "111"
    assert tasks[0].identity.task_type == "monday-items"
    assert tasks[0].title == "Active work"
    assert tasks[0].item == MondayItem(
        item_id="111",
        item_name="Active work",
        item_url="https://acme.monday.com/boards/1234567890/pulses/111",
        item_group_id="topics",
        item_group_title="Topics",
        board_id="1234567890",
        item_state="active",
        item_columns="status: Working on it",
    )


@pytest.mark.asyncio
async def test_empty_source_result_is_empty(tmp_path: Path) -> None:
    automation = resolved_automation(tmp_path, "board-items", "monday-items")
    assert await MondayItemSource(FakeMondayClient([])).discover(automation, 10) == []


@pytest.mark.asyncio
async def test_pagination_continues_across_polls_without_reemitting(tmp_path: Path) -> None:
    """Regression: when the first poll fills the batch, the next poll must use the cursor."""
    client = FakeMondayClient(
        [
            MondayItemsPage(
                items=(_board_item("1", "One"), _board_item("2", "Two")),
                cursor="next",
            ),
            MondayItemsPage(
                items=(_board_item("3", "Three"), _board_item("4", "Four")),
                cursor=None,
            ),
        ]
    )
    automation = resolved_automation(tmp_path, "board-items", "monday-items")
    feed = PollingTaskFeed(
        automation,
        PollingSettings(batch_size=2),
        MondayItemSource(client),
    )

    first = await feed.poll()
    second = await feed.poll()

    assert [task.identity.id for task in first] == ["1", "2"]
    assert [task.identity.id for task in second] == ["3", "4"]
    assert client.requests[0].cursor is None
    assert client.requests[1].cursor == "next"
    assert await feed.poll() == []


@pytest.mark.asyncio
async def test_discover_follows_cursor_within_one_call(tmp_path: Path) -> None:
    client = FakeMondayClient(
        [
            MondayItemsPage(items=(_board_item("1", "One"),), cursor="page-2"),
            MondayItemsPage(items=(_board_item("2", "Two"),), cursor=None),
        ]
    )
    automation = resolved_automation(tmp_path, "board-items", "monday-items")

    tasks = await MondayItemSource(client).discover(automation, 10)

    assert [task.identity.id for task in tasks] == ["1", "2"]
    assert client.requests[1].cursor == "page-2"


def test_monday_trigger_is_registered_and_exposes_prompt_fields(tmp_path: Path) -> None:
    trigger = get("monday-items")
    automation = resolved_automation(tmp_path, "board-items", "monday-items")
    task = Task(
        identity=TaskIdentity(
            automation_id="board-items",
            repo="api",
            task_type="monday-items",
            id="111",
        ),
        automation=automation,
        title="Active work",
        url="https://acme.monday.com/boards/1234567890/pulses/111",
        item=MondayItem(
            item_id="111",
            item_name="Active work",
            item_url="https://acme.monday.com/boards/1234567890/pulses/111",
            item_group_id="topics",
            item_group_title="Topics",
            board_id="1234567890",
            item_state="active",
            item_columns="status: Working on it",
        ),
    )

    assert isinstance(trigger, MondayItemTrigger)
    assert trigger.prompt_fields() == frozenset(
        {
            "item_id",
            "item_name",
            "item_url",
            "item_group_id",
            "item_group_title",
            "board_id",
            "item_state",
            "item_columns",
        }
    )
    assert trigger.prompt_context(task) == {
        "item_id": "111",
        "item_name": "Active work",
        "item_url": "https://acme.monday.com/boards/1234567890/pulses/111",
        "item_group_id": "topics",
        "item_group_title": "Topics",
        "board_id": "1234567890",
        "item_state": "active",
        "item_columns": "status: Working on it",
    }


def test_trigger_builds_shared_polling_feed(tmp_path: Path) -> None:
    automation = resolved_automation(tmp_path, "board-items", "monday-items")

    feed = MondayItemTrigger().build_feed(
        automation,
        FeedDependencies(
            polling=PollingSettings(),
            cron=CronScheduleRepository(tmp_path / "state.sqlite3"),
            state_db_path=tmp_path / "state.sqlite3",
        ),
    )

    assert isinstance(feed, PollingTaskFeed)
    assert feed.automation is automation


@pytest.mark.asyncio
async def test_end_to_end_mock_transport_group_filter(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        assert "group" in body
        assert "topics" in body
        payload: dict[str, Any] = {
            "data": {
                "boards": [
                    {
                        "items_page": {
                            "cursor": None,
                            "items": [
                                {
                                    "id": "55",
                                    "name": "Filtered",
                                    "url": "https://acme.monday.com/boards/1/pulses/55",
                                    "state": "active",
                                    "group": {"id": "topics", "title": "Topics"},
                                    "column_values": [],
                                }
                            ],
                        }
                    }
                ]
            }
        }
        return httpx.Response(200, json=payload)

    client = MondayClient(
        transport=httpx.MockTransport(handler),
        environ={"MONDAY_API_TOKEN": _TOKEN},
    )
    automation = resolved_automation(
        tmp_path, "board-items", "monday-items", group_ids=("topics",)
    )
    tasks = await MondayItemSource(client).discover(automation, 5)
    assert [task.identity.id for task in tasks] == ["55"]
