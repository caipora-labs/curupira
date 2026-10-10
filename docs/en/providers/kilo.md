# Kilo CLI

Install Kilo with npm:

```bash
npm install -g @kilocode/cli
```

Authenticate with `kilo auth login` or configure credentials for a supported model
provider in Kilo. Curupira does not store, request, or manage credentials; Kilo and its
provider integrations own authentication.

Curupira invokes `kilo run --format json` and sends the task message after `--`. Kilo's
JSONL events include a session ID on each record, and text parts use the same
`text`/`part.text` shape as OpenCode. Curupira therefore uses the shared session parser and
renderer, and resumes a saved session with `--session <session_id>`.

| Profile option | Native argument | Notes |
| --- | --- | --- |
| `model` | `--model <provider/model>` | Use Kilo's `provider/model` identifier. |
| `agent` | `--agent <agent>` | Name of an existing Kilo agent. |
| `effort` | `--variant <effort>` | Provider-specific reasoning variant such as `high`, `max`, or `minimal`. |
| `auto_approve` | `--auto` when `true` | Dangerous: auto-approves permissions that are not explicitly denied. |
| Session ID | `--session <session_id>` | Added by Curupira when resuming a task. |
| Task message | `-- <message>` | The separator keeps messages beginning with `-` from being parsed as flags. |

`effort` maps to `--variant`; Kilo's `--thinking` only displays thinking blocks and is not
used as a reasoning-effort option. Without `auto_approve`, Kilo rejects permission
requests during headless runs instead of waiting for interactive input. Leave
`auto_approve` disabled unless that broader permission behavior is intended.

::: curupira.agents.kilo.KiloCliProfile
