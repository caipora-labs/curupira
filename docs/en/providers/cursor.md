# Cursor

Curupira runs the [Cursor CLI](https://cursor.com/cli) (the `agent` command) in print
mode with streaming JSON output:

```text
agent --print --output-format stream-json [options] -- <prompt>
```

## Install and sign in { #install }

```sh
curl https://cursor.com/install -fsS | bash
agent login
```

The Cursor CLI owns authentication. Curupira never reads or stores credentials.

## Profile options { #options }

| Option | Native argument | Notes |
| --- | --- | --- |
| `model` | `--model <model>` | `auto` lets Cursor choose. |
| `agent` | `--mode <mode>` | `agent`, `ask`, or `plan`. |
| `force = true` | `--force` | Allows commands without confirmation. |
| `trust = true` | `--trust` | Trusts the workspace for this run. |
| `effort` | — | Not supported; rejected. |

## Example { #example }

```toml
[agents.profiles.cursor]
provider = "cursor"
model = "auto"
agent = "agent"
force = true
```

## Sessions { #sessions }

The session id from the JSON stream is saved with the task. An interrupted task resumes
with `--resume <session_id>`.
