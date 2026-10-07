# Providers and agents

OpsCli invokes each tool through its non-interactive native CLI and saves session identifiers to resume interrupted tasks. `model`, `effort`, and `agent` are optional; unset options are omitted.

| Provider | Agent mapping | Model | Effort |
| --- | --- | --- | --- |
| OpenCode | Custom agent via `--agent` | Optional `--model` | Optional `--variant` |
| Claude Code | Custom agent via `--agent` | Optional `--model` | Optional `--effort` |
| Codex | Config profile via `--profile` | Optional `--model` | `model_reasoning_effort` via `--config` |
| Cursor | Mode via `--mode` (`agent`, `ask`, or `plan`) | Optional `--model` | Unsupported; rejected |

## OpenCode

Runs `opencode run --format json`, passing a configured model, agent, and effort as `--model`, `--agent`, and `--variant`. Resumes sessions with `--session <session_id>`.

## Codex

Runs `codex exec --json`; resumes with `codex exec resume <thread_id>`. Effort is passed as `--config model_reasoning_effort=<level>`. Documented levels include `low`, `medium`, `high`, `xhigh`, `max`, and `ultra`; availability depends on the model and CLI version.

## Claude Code

Runs `claude -p --output-format stream-json --verbose`, passing configured model, agent, and effort through their native flags. Resumes with `--resume <session_id>`.

## Cursor

Runs `agent --print --output-format stream-json`, passing model with `--model` and mode with `--mode`. Effort is not supported.

Permission overrides are also provider-specific (`auto_approve` for OpenCode, `sandbox`/`auto_review` for Codex, `permission_mode`/`permission_prompts` for Claude Code, and `force`/`trust` for Cursor). If omitted, each CLI keeps its native policy.
