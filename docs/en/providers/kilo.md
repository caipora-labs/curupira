# Kilo CLI

Curupira runs the [Kilo CLI](https://kilocode.ai/cli) in `run` mode with JSON output:

```text
kilo run --format json [options] -- <prompt>
```

## Install and sign in { #install }

```sh
npm install -g @kilocode/cli
kilo auth login
```

Kilo and its provider integrations own authentication. Curupira never reads or stores
credentials.

## Profile options { #options }

| Option | Native argument | Notes |
| --- | --- | --- |
| `model` | `--model <provider/model>` | Must use the `provider/model` form; anything else is a configuration error. |
| `agent` | `--agent <agent>` | An existing Kilo agent. |
| `effort` | `--variant <variant>` | Provider-specific reasoning variant such as `high`, `max`, or `minimal`. |
| `auto_approve = true` | `--auto` | Approves permissions that are not explicitly denied. Use with care. |

Kilo's `--thinking` only displays thinking blocks, so it is not used for `effort`.
Without `auto_approve`, Kilo rejects permission requests in headless runs instead of
waiting for input.

## Example { #example }

```toml
[agents.profiles.kilo]
provider = "kilo"
model = "anthropic/claude-sonnet-4"
effort = "high"
```

## Sessions { #sessions }

Every JSON record carries the session id, which is saved with the task. An interrupted
task resumes with `--session <session_id>`.
