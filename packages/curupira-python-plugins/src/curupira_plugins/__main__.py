"""Official Curupira trigger extension process (all providers).

Console script ``curupira-plugins`` (also ``python -m curupira_plugins``) speaks
the extension protocol on stdin/stdout. End-user settings typically launch with::

    uvx --from curupira-plugins curupira-plugins
"""

from __future__ import annotations

import sys

from curupira_sdk import Curupira

from curupira_plugins import __version__
from curupira_plugins.github.triggers import register as register_github

app = Curupira(name="curupira-plugins", version=__version__)
register_github(app)

MANIFEST = """
manifest_version = 1
name = "curupira-plugins"
version = "{version}"
protocol_version = 1
runtime = "python"
kind = "trigger"
trigger_types = [
  "github-issues",
  "github-pull-requests",
  "github-project-items",
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
