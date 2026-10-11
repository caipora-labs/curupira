# TUI assistant

`curu tui` embeds a coding-agent assistant in a side panel, inspired by Omarchy-style
workflows where the coding agent stays inside the orchestrator UI instead of suspending
it.

## Shortcut

| Key | Action |
| --- | --- |
| `Ctrl+G` | Open or close the assistant side panel (half the screen). |

When the panel opens and `[assistant].agent` is unset, Curupira lists every coding-agent
provider registered in `curupira.agents` (built-ins and installed plugins). Choosing one
writes `agent` into the existing `[assistant]` table of your settings TOML—the same
place and format as the [configuration assistant settings](configuration.md#assistant).
Opening the panel again reuses that choice and starts a new interactive session.

## How the session starts

1. Resolve the model with `resolve_assistant_model` against the adapter's `auto_model`
   capability (unset `assistant.model` prefers native auto when the adapter declares it).
2. Build an `InteractiveLaunchSpec` from the adapter's `interactive_launch` recipe.
3. Host that command in the reusable `PtyTerminal` widget in the project working
   directory (`Path.cwd()` when `curu tui` was started), using the allowlisted PTY
   environment from `default_pty_env`.

If the adapter has no native `auto_model`, Curupira omits the model flag and shows a
short notice that the CLI's own default model applies. If the executable is missing from
`PATH`, the panel shows a clear install message instead of a stack trace. Closing the
panel (or quitting the TUI) unmounts `PtyTerminal`, which tears down the child process.

## Related configuration

See [`[assistant]`](configuration.md#assistant) for `agent` and `model` fields, and the
[agent plugin contract](plugins.md#agent-contract) for `interactive_launch` and
`auto_model` when extending Curupira with a new coding-agent adapter.
