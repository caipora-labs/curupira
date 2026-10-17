"""Official Trello card trigger."""

from __future__ import annotations

from dataclasses import dataclass

from curupira_sdk import Curupira


@dataclass
class Card:
    id: str
    name: str
    url: str
    desc: str = ""
    list_name: str = ""


def register(app: Curupira) -> None:
    """Register Trello triggers on ``app``."""

    @app.trigger
    def trello_cli_cards(
        board_id: str,
        list_ids: list[str] | None = None,
    ) -> Card | None:
        """Return the next eligible Trello card, or None when none are available."""
        del board_id, list_ids
        return None
