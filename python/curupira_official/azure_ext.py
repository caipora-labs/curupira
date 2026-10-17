"""Official Azure DevOps pull-request trigger extension."""

from __future__ import annotations

import re
import sys
from typing import Any

from curupira_official import __version__
from curupira_official._rpc import RpcError, serve

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_TRIGGERS = [
    {
        "trigger_type": "azure-cli-pull-requests",
        "prompt_fields": [
            "pull_request_number",
            "pull_request_title",
            "pull_request_body",
            "pull_request_url",
            "pull_request_head_ref",
            "pull_request_base_ref",
        ],
    }
]


def validate(params: Any) -> dict[str, Any]:
    config = dict((params or {}).get("configuration") or {})
    for key in ("repo", "repository", "prompt"):
        if key not in config or config[key] in (None, ""):
            raise RpcError(-32003, f"missing required field {key!r}")
    repo = config["repo"]
    if not isinstance(repo, str) or _REPO_RE.fullmatch(repo) is None:
        raise RpcError(-32003, "repo must use the organization/project/repository format")
    if any(part in {".", ".."} for part in repo.split("/")):
        raise RpcError(-32003, "repo must not contain traversal segments")
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
name = "curupira-azure"
version = "{version}"
protocol_version = 1
runtime = "python"
kind = "trigger"
trigger_types = ["azure-cli-pull-requests"]

[launch]
type = "executable"
program = "{python}"
args = ["-m", "curupira_official.azure_ext"]
""".strip()


def main() -> None:
    if "--curupira-print-manifest" in sys.argv:
        print(MANIFEST.format(version=__version__, python=sys.executable))
        return
    serve(
        name="curupira-azure",
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
