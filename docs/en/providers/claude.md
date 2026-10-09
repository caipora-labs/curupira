# Claude Code

Runs `claude -p --output-format stream-json --verbose`, passing configured model, agent, and effort through their native flags. Resumes with `--resume <session_id>`.

| Option | Native argument |
| --- | --- |
| `agent` | Custom agent via `--agent` |
| `model` | Optional `--model` |
| `effort` | Optional `--effort` |
