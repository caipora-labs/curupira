# Gemini CLI

Curupira runs [Gemini CLI](https://github.com/google-gemini/gemini-cli) non-interactively
with streaming JSON output:

```text
gemini --output-format stream-json [options] --prompt=<prompt>
```

## Install and sign in { #install }

Gemini CLI needs Node.js 20 or newer.

```sh
npm install -g @google/gemini-cli
gemini   # sign in once with your Google account
```

You can also set `GEMINI_API_KEY` or configure Vertex AI. Gemini CLI owns authentication;
Curupira never reads or stores credentials.

## Profile options { #options }

| Option | Native argument | Notes |
| --- | --- | --- |
| `model` | `--model <model>` | `auto` lets Gemini choose. |
| `approval_mode` | `--approval-mode <mode>` | `default`, `auto_edit`, `yolo`, or `plan`. Unset keeps Gemini's policy. |
| `skip_trust = true` | `--skip-trust` | Skips the folder trust check. |
| `agent` | — | Not supported; rejected. |
| `effort` | — | Not supported; rejected. |

!!! warning "`yolo` approves everything"
    `approval_mode = "yolo"` turns off approval prompts. Curupira passes
    `--approval-mode yolo` rather than the deprecated `--yolo` flag.

The prompt is passed as `--prompt=<prompt>`, so a prompt that starts with `-` stays text.

## Example { #example }

```toml
[agents.profiles.gemini]
provider = "gemini"
model = "auto"
approval_mode = "auto_edit"
```

## Sessions { #sessions }

The session id comes from Gemini's `init` event and is saved with the task. An
interrupted task resumes with `--resume <session_id>`.
