# TUI assistant

`curu tui` embeds a coding-agent assistant in a side panel. The coding agent runs
inside the panel so you do not need to suspend the TUI.

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
The saved agent applies the next time you open the panel; you do not need to restart the
TUI. Opening the panel again starts a new interactive session with that agent.

If `[assistant].model` is `"auto"` and the agent you pick has no native automatic model,
Curupira removes the `model` key from `[assistant]` when it saves the new agent.

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

1. The model comes from `[assistant].model`. When that key is unset, Curupira uses the
   provider's native automatic model when the adapter supports it; otherwise the CLI's
   own default applies (with a short notice).
2. The interactive command runs in the directory where you started `curu tui`.
3. Provider API keys are not forwarded into the embedded terminal; use the coding-agent
   CLI's own login.

If the executable is missing from `PATH`, the panel shows a clear install message instead
of a stack trace. Closing the panel (or quitting the TUI from the main dashboard) tears
down the child process. Window resize propagates to the PTY.

Persistence only rewrites a standard unquoted `[assistant]` table (atomic replace in the
same directory, preserving file mode, newline style (LF or CRLF), and end-of-line comments
on existing `agent` / `model` lines). Removing `model` drops that line without leaving an
extra blank in the section. It does not run a full TOML pretty-printer; other comments and
tables outside that section are left as-is.

## Related configuration

See [`[assistant]`](configuration.md#assistant) for `agent` and `model` fields, and the
[agent plugin contract](plugins.md#agent-contract) for `interactive_launch` and
`auto_model` when extending Curupira with a new coding-agent adapter.
