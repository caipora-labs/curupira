# Qwen Code

Install Qwen Code with Node.js 22 or later:

```bash
npm install -g @qwen-code/qwen-code@latest
```

Curupira runs `qwen --output-format stream-json --prompt=<message>`. It resumes a known
session with `--resume <session_id>`. Qwen Code owns authentication; Curupira does not
handle provider credentials.

| Profile option | Native argument |
| --- | --- |
| `model` | Optional `--model` |
| `approval_mode` | Optional `--approval-mode` (`plan`, `default`, `auto-edit`, `auto`, or `yolo`) |
| `max_session_turns` | Optional `--max-session-turns` (integer ≥ 1) |
| `agent` | Unsupported; rejected |
| `effort` | Unsupported; rejected |

`approval_mode = "yolo"` enables automatic approval. The Qwen Code documentation warns
that YOLO mode “does not enable a sandbox.”

The `--max-wall-time` and `--max-tool-calls` options are not exposed; Curupira's task
timeout bounds each run.

::: curupira.agents.qwen.QwenCodeCliProfile
