# TUI assistant

`curu tui` embeds a coding-agent assistant in a side panel, inspired by Omarchy-style
workflows where the coding agent stays inside the orchestrator UI instead of suspending
it.

## Shortcuts

| Key | Focus / context | Behavior |
| --- | --- | --- |
| `Ctrl+G` | Anywhere | Open or close the assistant side panel (half the screen). Closing tears down the PTY child. |
| `F6` | Panel open | Toggle keyboard focus between the assistant panel and the main dashboard **without** closing the panel. While the PTY has focus it would otherwise swallow dashboard keys (`F1` help, `F2` pause, `F3` config, `F5` refresh, and `Tab`); `F6` returns those shortcuts to the main TUI, and `F6` again returns typing to the agent. Chosen because coding-agent CLIs rarely bind it. |
| `Ctrl+C` | Assistant PTY focused | Interrupt the agent child (terminal `SIGINT`). Does **not** quit the TUI. |
| `Ctrl+C` | Main TUI focused | Quit Curupira and tear down any assistant child. |
| `Esc` | Assistant PTY focused | Forwarded to the agent (not used to close the panel). |
| `Esc` | Panel open, no PTY (picker or error) | Close the side panel. |

The Footer and Help screen (`F1`) list the same bindings.

## Choosing an agent

When the panel opens and `[assistant].agent` is unset, Curupira lists every coding-agent
provider registered in `curupira.agents` (built-ins and installed plugins). Choosing one
writes `agent` into the existing `[assistant]` table of your settings TOML—the same
place and format as the [configuration assistant settings](configuration.md#assistant).
Opening the panel again reuses that choice and starts a new interactive session.

!!! warning
    Saving the agent choice updates your settings TOML on disk. That file change triggers
    Curupira's hot-reload: new task admissions pause until in-flight work drains, then
    settings and feeds reload. Prefer choosing the agent when the orchestrator is idle if
    you want to avoid that pause.

If the config file cannot be written (missing, read-only, or an unsupported `assistant`
TOML shape such as an inline table, dotted key, or quoted header), the panel shows a
clear message, leaves the file untouched when the shape is unsupported, and still applies
the choice in memory for the current session.

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
panel (or quitting the TUI from the main dashboard) unmounts `PtyTerminal`, which tears
down the child process. Window resize propagates to the PTY via `TIOCSWINSZ` /
`SIGWINCH`.

Persistence only rewrites a standard unquoted `[assistant]` table (atomic replace in the
same directory, preserving file mode, newline style (LF or CRLF), and end-of-line comments
on existing `agent` / `model` lines). Removing `model` drops that line without leaving an
extra blank in the section. It does not run a full TOML pretty-printer; other comments and
tables outside that section are left as-is.

## Related configuration

See [`[assistant]`](configuration.md#assistant) for `agent` and `model` fields, and the
[agent plugin contract](plugins.md#agent-contract) for `interactive_launch` and
`auto_model` when extending Curupira with a new coding-agent adapter.
