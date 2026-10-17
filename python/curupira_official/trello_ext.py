"""Official Trello card trigger extension."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from curupira_official import __version__
from curupira_sdk import Curupira

app = Curupira(name="curupira-trello", version=__version__)


@dataclass
class Card:
    id: str
    name: str
    url: str
    desc: str = ""
    list_name: str = ""


@app.trigger
def trello_cli_cards(
    board_id: str,
    list_ids: list[str] | None = None,
) -> Card | None:
    """Return the next eligible Trello card, or None when none are available."""
    del board_id, list_ids
    return None


MANIFEST = """
manifest_version = 1
name = "curupira-trello"
version = "{version}"
protocol_version = 1
runtime = "python"
kind = "trigger"
trigger_types = ["trello_cli_cards"]

[launch]
type = "executable"
program = "{python}"
args = ["-m", "curupira_official.trello_ext"]
""".strip()


def main() -> None:
    if "--curupira-print-manifest" in sys.argv:
        app.print_manifest(MANIFEST)
        return
    app.run()


if __name__ == "__main__":
    main()
