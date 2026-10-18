# Codex

Curupira runs the [Codex CLI](https://github.com/openai/codex) non-interactively with JSON
events:

```text
codex exec [options] --json -- <prompt>
```

## Install and sign in { #install }

```sh
npm install -g @openai/codex
codex login
```

Codex owns authentication (a ChatGPT account or an API key). Curupira never reads or
stores credentials.

## Profile options { #options }

| Option | Native argument | Notes |
| --- | --- | --- |
| `model` | `--model <model>` | |
| `agent` | `--profile <name>` | A profile from your Codex `config.toml`. |
| `effort` | `--config model_reasoning_effort="<level>"` | For example `low`, `medium`, `high`, `xhigh`. Availability depends on the model. |
| `sandbox` | `--sandbox <mode>` | For example `workspace-write`. Unset keeps Codex's policy. |
| `auto_review = true` | `--config approval_policy="on-request"` and `--config approvals_reviewer="auto_review"` | Lets Codex review its own approval requests. |

Unset options add no argument.

## Example { #example }

```toml
[agents.profiles.codex]
provider = "codex"
model = "gpt-5-codex"
effort = "high"
sandbox = "workspace-write"
```

## Sessions { #sessions }

The thread id from the JSON events is saved with the task. An interrupted task resumes
with `codex exec resume <thread_id>`.
