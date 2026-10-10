"""Trello card task discovery and trigger behavior."""

from typing_extensions import override

from curupira.clients.trello import TrelloClient
from curupira.models import (
    ResolvedAutomation,
    Task,
    TaskIdentity,
    TrelloAutomationConfiguration,
    TrelloListRequest,
)
from curupira.tasks.base import FeedDependencies, TaskFeed, TaskSource, Trigger
from curupira.tasks.feed import PollingTaskFeed
from curupira.tasks.registry import register


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
                body=card.desc,
                url=card.url,
                attributes={"board_id": config.board_id, "list_id": card.id_list},
            )
            for card in cards
            if not card.closed
        ]
        return tasks[:limit]


class TrelloCardTrigger(Trigger):
    """Trigger implementation for Trello card automations."""

    trigger_type = "trello-cli-cards"
    configuration_model = TrelloAutomationConfiguration

    @classmethod
    @override
    def prompt_fields(cls) -> frozenset[str]:
        """Return the Trello-specific prompt placeholders."""
        return frozenset({"card_id", "card_title", "card_body", "card_url", "card_list_id"})

    @override
    def prompt_context(self, task: Task) -> dict[str, str]:
        """Map a Trello task into its card-specific prompt placeholders."""
        return {
            "card_id": task.identity.id,
            "card_title": task.title,
            "card_body": task.body or "",
            "card_url": task.url,
            "card_list_id": task.attributes.get("list_id", ""),
        }

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


register(TrelloCardTrigger())
