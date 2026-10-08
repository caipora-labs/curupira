# Codex

Runs `codex exec --json`; resumes with `codex exec resume <thread_id>`. Effort is passed as `--config model_reasoning_effort=<level>`. Documented levels include `low`, `medium`, `high`, `xhigh`, `max`, and `ultra`; availability depends on the model and CLI version.

| Option | Native argument |
| --- | --- |
| `agent` | Config profile via `--profile` |
| `model` | Optional `--model` |
| `effort` | `model_reasoning_effort` via `--config` |
