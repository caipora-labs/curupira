# Gemini CLI

Curupira runs Gemini CLI in non-interactive `stream-json` mode and resumes sessions
with Gemini's native `--resume <session_id>` option.

## Install

Gemini CLI requires Node.js 20 or newer. Install it globally with npm:

```bash
npm install -g @google/gemini-cli
```

## Authentication

Authentication is owned by Gemini CLI. Sign in through its Google account flow, set
`GEMINI_API_KEY`, or configure the environment for Vertex AI. Curupira does not read,
store, or manage provider credentials.

## Curupira options

Curupira maps the Gemini profile fields to these native arguments:

| Option | Native argument |
| --- | --- |
| `model` | Optional `--model <model>` |
| `approval_mode` | Optional `--approval-mode <mode>`: `default`, `auto_edit`, `yolo`, or `plan` |
| `skip_trust` | `--skip-trust` when `true` |
| `agent` | Unsupported; rejected |
| `effort` | Unsupported; rejected |

When `approval_mode` is unset, headless runs use Gemini CLI's native approval policy.
Setting it selects one of Gemini's explicit approval modes. **Warning:** setting
`approval_mode = "yolo"` disables approval prompts; use it only when that behavior is
intended. Curupira uses the `--approval-mode yolo` value rather than the deprecated
`--yolo` flag.

The prompt is passed as `--prompt=<message>`, keeping messages that start with `-` as
prompt text. Gemini's native session identifier is captured from its `init` event.

## Profile reference

{% if page.url == "providers/gemini/" %}
::: curupira.agents.gemini.GeminiCliProfile
{% endif %}
