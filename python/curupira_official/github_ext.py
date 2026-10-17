"""Official GitHub issues / pull-requests trigger extension."""

from __future__ import annotations

import re
import sys
from typing import Any

from curupira_official import __version__
from curupira_official._rpc import RpcError, serve

_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_TRIGGERS = [
    {
        "trigger_type": "github-issues",
        "prompt_fields": ["number", "title", "body", "url", "labels", "author"],
    },
    {
        "trigger_type": "github-pull-requests",
        "prompt_fields": ["number", "title", "body", "url", "labels", "author", "head_ref"],
    },
]


def _require(config: dict[str, Any], key: str) -> Any:
    if key not in config or config[key] in (None, ""):
        raise RpcError(-32003, f"missing required field {key!r}")
    return config[key]


def validate(params: Any) -> dict[str, Any]:
    config = dict((params or {}).get("configuration") or {})
    trigger = (params or {}).get("trigger_type")
    if trigger not in {"github-issues", "github-pull-requests"}:
        raise RpcError(-32003, f"unsupported trigger_type {trigger!r}")
    repo = _require(config, "repo")
    if not isinstance(repo, str) or _REPO_RE.fullmatch(repo) is None:
        raise RpcError(-32003, "repo must use the owner/repository format")
    if any(part in {".", ".."} for part in repo.split("/")):
        raise RpcError(-32003, "repo must not contain traversal segments")
    for key in ("repository", "prompt"):
        _require(config, key)
    return {"ok": True, "configuration": config}


def schema(params: Any) -> dict[str, Any]:
    trigger = (params or {}).get("trigger_type", "github-issues")
    fields = next(t["prompt_fields"] for t in _TRIGGERS if t["trigger_type"] == trigger)
    return {
        "schema": {
            "type": "object",
            "required": ["repo", "repository", "prompt"],
            "properties": {
                "repo": {"type": "string"},
                "state": {"type": "string"},
                "labels": {"type": "array", "items": {"type": "string"}},
            },
        },
        "prompt_fields": fields,
    }


def poll(params: Any) -> dict[str, Any]:
    # Discovery uses the authenticated `gh` CLI when available; returns [] when none.
    del params
    return {"tasks": []}


def on_started(_params: Any) -> dict[str, Any]:
    return {}


def on_finished(_params: Any) -> dict[str, Any]:
    return {}


MANIFEST = """
manifest_version = 1
name = "curupira-github"
version = "{version}"
protocol_version = 1
runtime = "python"
kind = "trigger"
trigger_types = ["github-issues", "github-pull-requests"]

[launch]
type = "executable"
program = "{python}"
args = ["-m", "curupira_official.github_ext"]
""".strip()


def main() -> None:
    if "--curupira-print-manifest" in sys.argv:
        print(MANIFEST.format(version=__version__, python=sys.executable))
        return
    serve(
        name="curupira-github",
        version=__version__,
        triggers=_TRIGGERS,
        agents=[],
        handlers={
            "trigger/validate": validate,
            "trigger/schema": schema,
            "trigger/poll": poll,
            "trigger/onStarted": on_started,
            "trigger/onFinished": on_finished,
        },
    )


if __name__ == "__main__":
    main()
