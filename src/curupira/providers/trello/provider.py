"""Trello card task discovery and trigger behavior."""

from collections.abc import Sequence

from typing_extensions import override

from curupira.clients.trello import TrelloClient
from curupira.hooks import hookimpl
from curupira.models import (
    ResolvedAutomation,
    Task,
    TaskIdentity,
    TrelloAutomationConfiguration,
    TrelloListRequest,
)
from curupira.models.items import TrelloCardItem
from curupira.tasks.base import FeedDependencies, TaskFeed, TaskSource, Trigger
from curupira.tasks.feed import PollingTaskFeed


class TrelloCardSource(TaskSource):
    """Discover Trello cards from the configured board using ``trello-cli``."""

    def __init__(self, client: TrelloClient) -> None:
        self._client = client

    @override
    async def discover(self, automation: ResolvedAutomation, limit: int) -> list[Task]:
        """Map configured-board cards to Curupira tasks with their original string IDs."""
        config = automation.configuration
        if not isinstance(config, TrelloAutomationConfiguration):
            raise ValueError("Trello card source requires a Trello card configuration")
        cards = await self._client.list_cards(
            TrelloListRequest(
                board_id=config.board_id,
                list_ids=config.list_ids,
            )
        )
        tasks = [
            Task(
                identity=TaskIdentity(
                    automation_id=automation.automation_id,
                    repo=config.repo,
                    task_type=config.trigger_type,
                    id=card.id,
                ),
                automation=automation,
                title=card.name,
                url=card.url,
                item=TrelloCardItem(
                    card_id=card.id,
                    card_title=card.name,
                    card_body=card.desc or "",
                    card_url=card.url,
                    card_list_id=card.id_list,
                ),
            )
            for card in cards
            if not card.closed
        ]
        return tasks[:limit]


class TrelloCardTrigger(Trigger):
    """Trigger implementation for Trello card automations."""

    trigger_type = "trello-cli-cards"
    configuration_model = TrelloAutomationConfiguration
    item_model = TrelloCardItem

    @override
    def build_feed(
        self, automation: ResolvedAutomation, dependencies: FeedDependencies
    ) -> TaskFeed:
        """Build the shared polling feed backed by Scale-Flow's Trello CLI."""
        return PollingTaskFeed(
            automation,
            dependencies.polling,
            TrelloCardSource(TrelloClient(dependencies.runner)),
        )


@hookimpl
def curupira_triggers() -> Sequence[Trigger]:
    """Contribute the Trello card trigger."""
    return (TrelloCardTrigger(),)
