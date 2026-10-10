"""Trello card source and trigger behavior."""

from pathlib import Path

import pytest
from typing_extensions import override

from curupira.clients.trello import TrelloClient
from curupira.models import PollingSettings, Task, TaskIdentity, TrelloCard, TrelloListRequest
from curupira.models.items import TrelloCardItem
from curupira.storage import CronScheduleRepository
from curupira.tasks.base import FeedDependencies
from curupira.tasks.feed import PollingTaskFeed
from curupira.tasks.registry import get
from curupira.tasks.trello_cards import TrelloCardSource, TrelloCardTrigger
from tests.helpers import resolved_automation


class FakeTrelloClient(TrelloClient):
    """Return controlled cards and retain the board/list request."""

    def __init__(self, cards: list[TrelloCard]) -> None:
        super().__init__()
        self.cards = cards
        self.requests: list[TrelloListRequest] = []

    @override
    async def list_cards(self, request: TrelloListRequest) -> list[TrelloCard]:
        self.requests.append(request)
        return self.cards


def card(card_id: str = "66f6b55a1a2b3c4d5e6f7788", *, closed: bool = False) -> TrelloCard:
    """Build a typed card payload with a deliberately non-integer ID."""
    return TrelloCard(
        id=card_id,
        name="Ship feature",
        desc="Details",
        url="https://trello.com/c/abc123",
        idList="list-1",
        closed=closed,
    )


@pytest.mark.asyncio
async def test_source_maps_cards_preserving_id_and_filters_closed_cards(tmp_path: Path) -> None:
    client = FakeTrelloClient([card(), card("archived", closed=True)])
    automation = resolved_automation(
        tmp_path,
        "board-tasks",
        "trello-cli-cards",
        board_id="board-1",
        list_ids=("list-1",),
    )

    tasks = await TrelloCardSource(client).discover(automation, 8)

    assert client.requests == [TrelloListRequest(board_id="board-1", list_ids=("list-1",))]
    assert len(tasks) == 1
    assert tasks[0].identity.id == "66f6b55a1a2b3c4d5e6f7788"
    assert tasks[0].identity.task_type == "trello-cli-cards"
    assert tasks[0].title == "Ship feature"
    assert tasks[0].url == "https://trello.com/c/abc123"
    assert tasks[0].item == TrelloCardItem(
        card_id="66f6b55a1a2b3c4d5e6f7788",
        card_title="Ship feature",
        card_body="Details",
        card_url="https://trello.com/c/abc123",
        card_list_id="list-1",
    )


@pytest.mark.asyncio
async def test_empty_source_result_is_empty(tmp_path: Path) -> None:
    automation = resolved_automation(tmp_path, "board-tasks", "trello-cli-cards")

    assert await TrelloCardSource(FakeTrelloClient([])).discover(automation, 10) == []


@pytest.mark.asyncio
async def test_repeated_poll_deduplicates_cards(tmp_path: Path) -> None:
    automation = resolved_automation(tmp_path, "board-tasks", "trello-cli-cards")
    feed = PollingTaskFeed(
        automation,
        PollingSettings(),
        TrelloCardSource(FakeTrelloClient([card()])),
    )

    assert len(await feed.poll()) == 1
    assert await feed.poll() == []


def test_trello_trigger_is_registered_and_exposes_card_prompt_fields(tmp_path: Path) -> None:
    trigger = get("trello-cli-cards")
    automation = resolved_automation(tmp_path, "board-tasks", "trello-cli-cards")
    task = Task(
        identity=TaskIdentity(
            automation_id="board-tasks",
            repo="acme/api",
            task_type="trello-cli-cards",
            id="card-id-123",
        ),
        automation=automation,
        title="Ship feature",
        url="https://trello.com/c/abc123",
        item=TrelloCardItem(
            card_id="card-id-123",
            card_title="Ship feature",
            card_body="Details",
            card_url="https://trello.com/c/abc123",
            card_list_id="list-1",
        ),
    )

    assert isinstance(trigger, TrelloCardTrigger)
    assert trigger.prompt_fields() == frozenset(
        {"card_id", "card_title", "card_body", "card_url", "card_list_id"}
    )
    assert trigger.prompt_context(task) == {
        "card_id": "card-id-123",
        "card_title": "Ship feature",
        "card_body": "Details",
        "card_url": "https://trello.com/c/abc123",
        "card_list_id": "list-1",
    }


def test_trigger_builds_shared_polling_feed(tmp_path: Path) -> None:
    automation = resolved_automation(tmp_path, "board-tasks", "trello-cli-cards")

    feed = TrelloCardTrigger().build_feed(
        automation,
        FeedDependencies(
            polling=PollingSettings(),
            cron=CronScheduleRepository(tmp_path / "state.sqlite3"),
            state_db_path=tmp_path / "state.sqlite3",
        ),
    )

    assert isinstance(feed, PollingTaskFeed)
    assert feed.automation is automation
