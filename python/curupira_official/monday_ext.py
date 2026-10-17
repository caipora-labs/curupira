"""Official monday.com items trigger extension."""

from __future__ import annotations

import sys
from typing import Any

from curupira_official import __version__
from curupira_official._rpc import RpcError, serve

_TRIGGERS = [
    {
        "trigger_type": "monday-items",
        "prompt_fields": ["id", "name", "url", "board_id", "group_title"],
    }
]


def validate(params: Any) -> dict[str, Any]:
    config = dict((params or {}).get("configuration") or {})
    for key in ("board_id", "repository", "prompt"):
        if key not in config or config[key] in (None, ""):
            raise RpcError(-32003, f"missing required field {key!r}")
    return {"ok": True, "configuration": config}


def schema(_params: Any) -> dict[str, Any]:
    return {
        "schema": {"type": "object"},
        "prompt_fields": _TRIGGERS[0]["prompt_fields"],
    }


def poll(_params: Any) -> dict[str, Any]:
    return {"tasks": []}


MANIFEST = """
manifest_version = 1
name = "curupira-monday"
version = "{version}"
protocol_version = 1
runtime = "python"
kind = "trigger"
trigger_types = ["monday-items"]

[launch]
type = "executable"
program = "{python}"
args = ["-m", "curupira_official.monday_ext"]
""".strip()


def main() -> None:
    if "--curupira-print-manifest" in sys.argv:
        print(MANIFEST.format(version=__version__, python=sys.executable))
        return
    serve(
        name="curupira-monday",
        version=__version__,
        triggers=_TRIGGERS,
        agents=[],
        handlers={
            "trigger/validate": validate,
            "trigger/schema": schema,
            "trigger/poll": poll,
            "trigger/onStarted": lambda _p: {},
            "trigger/onFinished": lambda _p: {},
        },
    )


if __name__ == "__main__":
    main()
