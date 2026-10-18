# Claude Code

Curupira runs [Claude Code](https://docs.anthropic.com/en/docs/claude-code) in print mode
with streaming JSON output:

```text
claude -p --output-format stream-json --verbose [options] -- <prompt>
```

## Install and sign in { #install }

```sh
npm install -g @anthropic-ai/claude-code
claude   # sign in once, interactively
```

Claude Code owns authentication (an Anthropic account or `ANTHROPIC_API_KEY`). Curupira
never reads or stores credentials.

## Profile options { #options }

| Option | Native argument | Notes |
| --- | --- | --- |
| `model` | `--model <model>` | An alias such as `sonnet` or a full model id. |
| `agent` | `--agent <agent>` | A custom agent defined in Claude Code. |
| `effort` | `--effort <level>` | Reasoning effort level. |
| `permission_mode` | `--permission-mode <mode>` | For example `acceptEdits` or `plan`. Unset keeps Claude Code's default. |
| `permission_prompts` | `--permission-prompts <value>` | Passed through unchanged. |

Unset options add no argument. The prompt always follows `--`, so a prompt that starts
with `-` is not read as a flag.

## Example { #example }

```toml
[agents.profiles.claude]
provider = "claude"
model = "sonnet"
permission_mode = "acceptEdits"
```

## Sessions { #sessions }

The session id from the JSON stream is saved with the task. An interrupted task resumes
with `--resume <session_id>`.
