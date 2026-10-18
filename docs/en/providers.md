# Coding agents

Curupira does not ship a model or call an LLM API. It starts the coding-agent CLI you
already use, in non-interactive mode, inside the task's worktree. Your login, model
access, and agent settings stay in that CLI.

## Supported agents { #supported }

{{ agents_table() }}

Every adapter is built into Curupira. Adding an agent is a change to Curupira itself, not
a plugin.

## Profiles { #profiles }

A profile is a named way to run one agent. Define as many as you need and pick one per
automation:

```toml
[agents.defaults]
profile = "claude"            # used when an automation sets no profile
timezone = "UTC"

[agents.profiles.claude]
provider = "claude"
model = "sonnet"

[agents.profiles.codex-high]
provider = "codex"
effort = "high"

[automations.review-ready-prs]
trigger_type = "plugins-py/github-pull-requests"
repository = "api"
repo = "acme/api"
profile = "codex-high"        # this automation uses Codex
prompt = "Review pull request #${pr_number}."
```

`model`, `agent`, and `effort` are optional and mean the same thing everywhere; each
agent page shows the native flag they become. An option you leave out adds no argument,
so the CLI keeps its own default. An option the agent does not support is a configuration
error, not silently ignored.

## Permissions { #permissions }

Unattended runs cannot answer permission prompts. Each CLI has its own switches, and
Curupira only passes the ones you set:

| Agent | Options |
| --- | --- |
| [Claude Code](providers/claude.md) | `permission_mode`, `permission_prompts` |
| [Codex](providers/codex.md) | `sandbox`, `auto_review` |
| [Cursor](providers/cursor.md) | `force`, `trust` |
| [Gemini CLI](providers/gemini.md) | `approval_mode`, `skip_trust` |
| [GitHub Copilot CLI](providers/copilot.md) | `allow_all_tools`, `allow_tools`, `deny_tools` |
| [Kilo CLI](providers/kilo.md) and [OpenCode](providers/opencode.md) | `auto_approve` |
| [pi](providers/pi.md) | `tools`, `exclude_tools`, `approve` |
| [Qwen Code](providers/qwen.md) | `approval_mode`, `max_session_turns` |

!!! warning "Task text is untrusted"
    Issue and pull-request text ends up in the prompt. Broad permissions plus a public
    repository let anyone who can open an issue steer the agent. Read
    [Security](github.md#security) before you loosen permissions.

## Sessions and limits { #sessions }

Curupira saves each agent's session id with the task and resumes it if the process stops
before the task finishes. Every run is bounded by `[settings].task_timeout_minutes`
(default `20`) and `[settings].max_output_bytes`.
