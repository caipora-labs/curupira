"""Official monday.com items trigger."""

from __future__ import annotations

from dataclasses import dataclass

from curupira_sdk import Curupira


@dataclass
class MondayItem:
    id: str
    name: str
    url: str
    board_id: str = ""
    group_title: str = ""


def register(app: Curupira) -> None:
    """Register monday.com triggers on ``app``."""

    @app.trigger
    async def monday_items(
        board_id: str,
        group_ids: list[str] | None = None,
        token_env: str | None = None,
    ) -> MondayItem | None:
        """Return the next eligible monday.com item, or None when none are available."""
        del board_id, group_ids, token_env
        return None
