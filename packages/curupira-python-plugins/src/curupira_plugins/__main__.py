"""Official Curupira trigger extension process (all providers).

Console script ``curupira-plugins`` (also ``python -m curupira_plugins``) speaks
the extension protocol on stdin/stdout. End-user settings typically launch with::

    uvx --from curupira-plugins curupira-plugins
"""

from __future__ import annotations

import sys

from curupira_sdk import Curupira

from curupira_plugins import __version__
from curupira_plugins.azure.triggers import register as register_azure
from curupira_plugins.github.triggers import register as register_github
from curupira_plugins.monday.triggers import register as register_monday
from curupira_plugins.trello.triggers import register as register_trello

app = Curupira(name="curupira-plugins", version=__version__)
register_github(app)
register_azure(app)
register_trello(app)
register_monday(app)

MANIFEST = """
manifest_version = 1
name = "curupira-plugins"
version = "{version}"
protocol_version = 2
runtime = "python"
kind = "trigger"
trigger_types = [
  "github-issues",
  "github-pull-requests",
  "azure-cli-pull-requests",
  "trello-cli-cards",
  "monday-items",
]

[launch]
type = "uvx"
package = "curupira-plugins"
executable = "curupira-plugins"

[package]
source = "pip"
name = "curupira-plugins"
version = "{version}"
""".strip()


def main() -> None:
    if "--curupira-print-manifest" in sys.argv:
        app.print_manifest(MANIFEST)
        return
    app.run()


if __name__ == "__main__":
    main()
