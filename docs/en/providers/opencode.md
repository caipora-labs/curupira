# OpenCode

Curupira runs [OpenCode](https://opencode.ai) in `run` mode with JSON output, pointed at
the task worktree:

```text
opencode run --format json --dir <worktree> [options] -- <prompt>
```

## Install and sign in { #install }

```sh
npm install -g opencode-ai
opencode auth login
```

OpenCode owns authentication for each model provider. Curupira never reads or stores
credentials.

## Profile options { #options }

| Option | Native argument | Notes |
| --- | --- | --- |
| `model` | `--model <provider/model>` | |
| `agent` | `--agent <agent>` | A custom OpenCode agent. |
| `effort` | `--variant <variant>` | Provider-specific reasoning variant. |
| `auto_approve = true` | `--auto` | Approves permissions that are not explicitly denied. Use with care. |

Each run sets `OPENCODE_DB` to a database next to the worktree, so parallel tasks do not
share OpenCode state.

## Example { #example }

```toml
[agents.profiles.opencode]
provider = "opencode"
model = "anthropic/claude-sonnet-4"
agent = "build"
```

## Sessions { #sessions }

The session id from the JSON events is saved with the task. An interrupted task resumes
with `--session <session_id>`.
