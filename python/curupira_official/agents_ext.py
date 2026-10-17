"""Official coding-agent adapters as one process extension."""

from __future__ import annotations

import sys
from typing import Any

from curupira_sdk import Curupira, RpcError

from curupira_official import __version__

_AGENTS = [
    {"provider": "opencode", "executable": "opencode"},
    {"provider": "claude", "executable": "claude"},
    {"provider": "codex", "executable": "codex"},
    {"provider": "cursor", "executable": "agent"},
    {"provider": "gemini", "executable": "gemini"},
    {"provider": "copilot", "executable": "copilot"},
    {"provider": "kilo", "executable": "kilo"},
    {"provider": "pi", "executable": "pi"},
    {"provider": "qwen", "executable": "qwen"},
]

_EXECUTABLE = {a["provider"]: a["executable"] for a in _AGENTS}

app = Curupira(name="curupira-agents", version=__version__, agents=_AGENTS)


def build_arguments(params: Any) -> dict[str, Any]:
    provider = (params or {}).get("provider")
    profile = dict((params or {}).get("profile") or {})
    request = dict((params or {}).get("request") or {})
    prompt = str(request.get("prompt") or "")
    if provider not in _EXECUTABLE:
        raise RpcError(-32002, f"unknown provider {provider!r}")
    exe = _EXECUTABLE[provider]
    argv: list[str]
    if provider == "opencode":
        argv = [exe, "run", "--format", "json"]
        if profile.get("model"):
            argv.extend(["--model", str(profile["model"])])
        if profile.get("agent"):
            argv.extend(["--agent", str(profile["agent"])])
        if profile.get("effort"):
            argv.extend(["--variant", str(profile["effort"])])
        if profile.get("auto_approve"):
            argv.append("--auto")
        argv.extend(["--", prompt])
    elif provider == "claude":
        argv = [exe, "-p", prompt, "--output-format", "stream-json"]
        if profile.get("model"):
            argv.extend(["--model", str(profile["model"])])
        if profile.get("agent"):
            argv.extend(["--agent", str(profile["agent"])])
        if profile.get("permission_mode"):
            argv.extend(["--permission-mode", str(profile["permission_mode"])])
    elif provider == "codex":
        argv = [exe, "exec", "--json"]
        if profile.get("model"):
            argv.extend(["--model", str(profile["model"])])
        if profile.get("agent"):
            argv.extend(["--profile", str(profile["agent"])])
        if profile.get("sandbox"):
            argv.extend(["--sandbox", str(profile["sandbox"])])
        argv.append(prompt)
    elif provider == "cursor":
        argv = [exe, "-p", prompt, "--output-format", "stream-json"]
        if profile.get("model"):
            argv.extend(["--model", str(profile["model"])])
        if profile.get("agent"):
            argv.extend(["--mode", str(profile["agent"])])
        if profile.get("trust"):
            argv.append("--trust")
        if profile.get("force"):
            argv.append("--force")
    elif provider == "gemini":
        argv = [exe, "--prompt", prompt, "--output-format", "stream-json"]
        if profile.get("model"):
            argv.extend(["--model", str(profile["model"])])
        if profile.get("approval_mode"):
            argv.extend(["--approval-mode", str(profile["approval_mode"])])
    elif provider == "copilot":
        argv = [exe, "-p", prompt, "--output-format", "json"]
        if profile.get("model"):
            argv.extend(["--model", str(profile["model"])])
        if profile.get("agent"):
            argv.extend(["--agent", str(profile["agent"])])
    elif provider == "kilo":
        argv = [exe, "run", "-p", prompt]
        if profile.get("model"):
            argv.extend(["--model", str(profile["model"])])
        if profile.get("agent"):
            argv.extend(["--agent", str(profile["agent"])])
        if profile.get("effort"):
            argv.extend(["--variant", str(profile["effort"])])
    elif provider == "pi":
        argv = [exe, "--print", prompt]
        if profile.get("model"):
            argv.extend(["--model", str(profile["model"])])
    elif provider == "qwen":
        argv = [exe, "--prompt", prompt, "--output-format", "stream-json"]
        if profile.get("model"):
            argv.extend(["--model", str(profile["model"])])
        if profile.get("approval_mode"):
            argv.extend(["--approval-mode", str(profile["approval_mode"])])
    else:
        raise RpcError(-32002, f"unhandled provider {provider!r}")
    return {"argv": argv, "env": []}


def interactive_launch(params: Any) -> dict[str, Any]:
    provider = (params or {}).get("provider")
    if provider == "opencode":
        return {
            "spec": {
                "program": "opencode",
                "args": [],
                "env": [],
            }
        }
    return {"spec": None}


MANIFEST = """
manifest_version = 1
name = "curupira-agents"
version = "{version}"
protocol_version = 1
runtime = "python"
kind = "agent"
agent_providers = ["opencode", "claude", "codex", "cursor", "gemini", "copilot", "kilo", "pi", "qwen"]

[launch]
type = "executable"
program = "{python}"
args = ["-m", "curupira_official.agents_ext"]
""".strip()


def main() -> None:
    if "--curupira-print-manifest" in sys.argv:
        app.print_manifest(MANIFEST)
        return
    app.on("agent/buildArguments", build_arguments)
    app.on("agent/interactiveLaunch", interactive_launch)
    app.run()


if __name__ == "__main__":
    main()
