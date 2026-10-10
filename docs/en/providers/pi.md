# pi

Curupira runs pi in JSON mode with `pi --mode json ... -- <message>`. A new session ID
comes from pi's JSONL session header and is resumed with `--session <id>`. pi groups
sessions by working directory; Curupira's deterministic task worktrees keep resumed runs
in the same project directory.

## Install

Install pi globally with npm. It requires Node.js 22.19.0 or later.

```sh
npm install -g @earendil-works/pi-coding-agent
node --version
```

Authenticate pi with the selected model provider's API-key environment variables or use
pi's `/login` command. Curupira does not collect, store, or forward credentials; the pi
process uses the user's configured environment and authentication.

## Profile options

| Curupira option | pi argument | Notes |
| --- | --- | --- |
| `model` | `--model <model>` | Exact or fuzzy model pattern; may include `provider/id`. |
| `model_provider` | `--provider <provider>` | Requires `model`; avoids a name collision with Curupira's `provider` discriminator. |
| `effort` | `--thinking <level>` | `off`, `minimal`, `low`, `medium`, `high`, `xhigh`, or `max`. |
| `tools` | `--tools a,b` | Comma-separated allowlist of tools pi can use. |
| `exclude_tools` | `--exclude-tools a,b` | Comma-separated tools to exclude. |
| `approve = true` | `--approve` | Explicitly trust the current project for this process. |
| `approve = false` | `--no-approve` | Explicitly do not trust the current project for this process. |
| `approve` omitted | *(no argument)* | Leave pi's configured project-trust behavior unchanged. |

pi does not ask for approval before each tool call, and its JSON mode cannot display the
project-trust prompt. When the configured default trust is `ask`, pi skips protected
project resources unless the invocation makes an explicit choice. Set `approve` only when
that project-level trust decision is intended. Use `tools` to limit the allowlist,
`exclude_tools` to remove specific tools, and Curupira's per-task worktrees to isolate
repository changes. pi has no native custom-agent option, so Curupira profiles do not
accept `agent`.

Curupira appends every prompt after `--`, so a leading dash is passed as prompt text. pi
also treats `@path` as a file include: a prompt beginning with `@` may be read as a file
reference rather than ordinary text.

```toml
[coding_agents.profiles.pi]
provider = "pi"
model = "anthropic/claude-sonnet-4"
model_provider = "anthropic"
effort = "high"
tools = ["read", "edit", "write"]
exclude_tools = ["bash"]
# approve = true # explicitly trust project resources for this process
```

The session identifier pi emits is persisted and resumed in the same deterministic task
worktree. Curupira uses the final assistant `message_end` event and joins its text blocks;
thinking and tool-call content are not shown as the task result.

::: curupira.agents.pi.PiCliProfile
