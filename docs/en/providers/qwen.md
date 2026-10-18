# Qwen Code

Curupira runs [Qwen Code](https://github.com/QwenLM/qwen-code) non-interactively with
streaming JSON output:

```text
qwen --output-format stream-json [options] --prompt=<prompt>
```

## Install and sign in { #install }

Qwen Code needs Node.js 22 or newer.

```sh
npm install -g @qwen-code/qwen-code@latest
qwen   # sign in once
```

Qwen Code owns authentication. Curupira never reads or stores credentials.

## Profile options { #options }

| Option | Native argument | Notes |
| --- | --- | --- |
| `model` | `--model <model>` | |
| `approval_mode` | `--approval-mode <mode>` | `plan`, `default`, `auto-edit`, `auto`, or `yolo`. |
| `max_session_turns` | `--max-session-turns <n>` | An integer of at least `1`. |
| `agent` | — | Not supported; rejected. |
| `effort` | — | Not supported; rejected. |

!!! warning "`yolo` is not a sandbox"
    `approval_mode = "yolo"` approves every action automatically. The Qwen Code
    documentation warns that it "does not enable a sandbox."

`--max-wall-time` and `--max-tool-calls` are not exposed; Curupira's
`task_timeout_minutes` bounds each run.

## Example { #example }

```toml
[agents.profiles.qwen]
provider = "qwen"
approval_mode = "auto-edit"
max_session_turns = 40
```

## Sessions { #sessions }

The session id from the JSON stream is saved with the task. An interrupted task resumes
with `--resume <session_id>`.
