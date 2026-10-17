"""Official monday.com items trigger extension."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from curupira_sdk import Curupira

from curupira_monday import __version__

app = Curupira(name="curupira-monday", version=__version__)


@dataclass
class MondayItem:
    id: str
    name: str
    url: str
    board_id: str = ""
    group_title: str = ""


@app.trigger
async def monday_items(
    board_id: str,
    group_ids: list[str] | None = None,
    token_env: str | None = None,
) -> MondayItem | None:
    """Return the next eligible monday.com item, or None when none are available."""
    del board_id, group_ids, token_env
    return None


MANIFEST = """
manifest_version = 1
name = "curupira-monday"
version = "{version}"
protocol_version = 1
runtime = "python"
kind = "trigger"
trigger_types = ["monday_items"]

[launch]
type = "executable"
program = "{python}"
args = ["-m", "curupira_monday"]
""".strip()


def main() -> None:
    if "--curupira-print-manifest" in sys.argv:
        app.print_manifest(MANIFEST)
        return
    app.run()


if __name__ == "__main__":
    main()
