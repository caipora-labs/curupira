# Terminal dashboard

`curupira tui` (or `curu tui`) opens an interactive dashboard and runs the same continuous
dispatch loop as `curupira run --watch` in the background.

```sh
curupira tui
```

## Layout { #layout }

`curupira tui` opens with the Curupira logo centered on the screen while the background
dispatch starts. It gives way to the dashboard after about a
second; press any key or click to skip it.

The dashboard has two columns:

- **Sidebar.** About a fifth of the width. The Curupira logo and version, the `[ Home ]` button,
  and the registered repositories. Under each repository name are the sessions for that
  repository. An orange dot beside the name means an agent is running there; a repository
  with no session is dimmed. Each session shows its name and its agent.
- **Workspace.** A header, the conversation history, and the `curupira > ` input fixed at the
  bottom. On Home, the header reads `DEFAULT AGENT - (<current directory>)`. With a session
  open, it reads `ATTACHED: <session> - <agent>`.

The layout follows the terminal size. Below 48 × 12 the dashboard asks you to enlarge the
terminal.

## Sessions { #sessions }

Every task the background dispatch starts opens a session under its repository
(`[repositories.<alias>]`) in the sidebar. Repositories stay listed when they have no
session, so the sidebar shows where an agent is working. A session takes the name
the coding agent gives its session: OpenCode titles a session a few seconds after it starts,
and the dashboard reads that title from `opencode session list`. Until then, and for agents
that do not expose session titles, the session is named after its issue or pull request
(`#223 bump paths-filter`) or its automation, which also stays in the session details. The dot
beside a repository is orange while one of its agents is running, and absent otherwise. The
dot beside a session shows that session's state:
orange while the agent runs, green when it finished, red when it failed. `N running` next to
the `REPOSITORIES` title counts the running ones, when the sidebar is wide enough to show it.

Open a session to follow its agent live: the automation and link, the prompt it received, the
agent's messages and tool calls as it reports them, and how it ended, with the agent's own
error message when it fails. Sessions last while the dashboard is open.

A message you type in a session is added to its history and marked as not sent: the
dashboard cannot pass messages to a running agent yet.

## Keyboard { #keyboard }

| Key | Sidebar focused | Input focused |
| --- | --- | --- |
| ++tab++ | Focus the input | Focus the sidebar |
| ++up++ / ++down++ | Select a session | Scroll the history |
| ++enter++ | Open the selected session | Submit the message |
| `h` | Go back to Home | Typed into the input |
| `q` | Quit | Typed into the input |
| ++page-up++ / ++page-down++ | Scroll the history | Scroll the history |
| ++left++ / ++right++, ++home++ / ++end++, ++backspace++, ++delete++ | — | Edit the message |
| ++esc++, ++ctrl+c++ | Quit | Quit |
| ++ctrl+l++ | Repaint the screen | Repaint the screen |

The input has focus when the dashboard opens. Going back to Home keeps every session and its
history.

## Mouse { #mouse }

- Click `[ Home ]` to go back to Home.
- Click a session (either of its two lines) to open it. Repository names are not buttons.
- Click the input to focus it and place the cursor.
- Scroll over the sidebar to move the repository list, or over the history to read older
  messages. Scrolling back to the bottom follows new messages again.

Clicks elsewhere do nothing.

## Background dispatch { #dispatch }

While the dashboard is open, Curupira polls every automation and runs tasks exactly like
`run --watch`:

- Started, finished (`done`), and failed tasks are listed by title in the Home history. The status at the
  bottom right shows `dispatch idle`, how many tasks are running, or `dispatch failed`.
- The dashboard holds `~/.curupira/dispatch.lock`, so it cannot run next to another `run` or
  `tui`.
- Quitting stops admitting work. If tasks are still running, Curupira prints how many and waits
  for them; press ++ctrl+c++ to stop them.
- A ++ctrl+c++ sent as a signal (for example `kill -INT`) exits with status `130`. Quitting
  with `q`, ++esc++, or the ++ctrl+c++ key exits with status `0`, or with the dispatch error if
  tasks failed.
- On Linux and macOS, everything written to stderr while the dashboard is open (logs,
  extension and agent messages) goes to `~/.curupira/logs/tui.log`, so it cannot draw over
  the screen.

Everything on [Running Curupira](operations.md) about polling, concurrency, and exit
codes applies to `tui` as well.

## Without a terminal { #status-mode }

When stdin or stdout is not a terminal (for example under a service manager or with output
piped), `tui` runs in **status mode**. It prints
`TUI: no terminal attached; running dispatch in status mode (Ctrl+C to stop)` on stderr and then
behaves exactly like `run --watch`, printing `ok` and `fail` lines.

## Logo { #logo }

The logo is pixel art drawn with half-block characters (`▀`, `▄`) in 24-bit color: the flame
beside a light `Curupira` wordmark. The splash shows it centered at its natural size. The
sidebar shows it when the sidebar is wide enough, and the flame with the name as text
otherwise. The dashboard uses no emoji. Terminals without 24-bit color show approximate colors.

## The `[assistant]` table { #assistant }

`[assistant]` names the default agent shown on Home. Curupira reads and validates it:

```toml
[assistant]
agent = "claude"   # a built-in provider name, checked by `curupira validate`
model = "sonnet"   # optional
```

An unknown `agent` is a configuration error. See
[Configuration](configuration.md#assistant) for the field reference.
