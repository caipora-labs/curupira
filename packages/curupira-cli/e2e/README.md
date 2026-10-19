# TUI end-to-end tests

These tests run the real `curupira tui` binary in a terminal emulator driven by
[`@microsoft/tui-test`](https://github.com/microsoft/tui-test). They press keys, click with the
mouse, resize the terminal, and read the screen the way a person would.

Every run is sandboxed by `lib/harness.mjs`: a temporary `HOME` and state database, a local
bare Git repository, and a fake `opencode` (`lib/fake-opencode.sh`) on `PATH` that prints
OpenCode 2.x JSON events. Nothing touches `~/.curupira`, the network, or a real coding agent.

## Run the tests

```bash
cargo build --manifest-path packages/curupira-cli/Cargo.toml --bin curupira
npm --prefix packages/curupira-cli/e2e install
npm --prefix packages/curupira-cli/e2e test
```

`CURUPIRA_BIN` points the tests at another binary. `tests/sessions.test.mjs` waits for a cron
automation to fire at the next minute boundary, so the suite takes up to about a minute and a half.

When an expectation fails, tui-test writes a trace to `artifacts/traces/`: open `trace.html` in a
browser, or read `trace.md`. `artifacts/failures/` keeps the screen text and recording.

## Inspect the TUI step by step

`npm run inspect` starts the TUI, runs the steps you give it, and saves the screen as text and
SVG after each one in `artifacts/inspect/`:

```bash
npm --prefix packages/curupira-cli/e2e run inspect -- --live --size 140x40 \
  --step "wait:Revisão automática" --step "session:Revisão automática" --step "wait:Task finished." \
  --step "key:Tab" --step "resize:80x24"
```

| Step | Does |
| --- | --- |
| `wait:TEXT` | Wait until `TEXT` is on screen (up to 90 s) |
| `gone:TEXT` | Wait until `TEXT` disappears |
| `click:TEXT` | Click the first match of `TEXT` |
| `session:NAME` | Click the sidebar session `NAME` (Home may show the same text first) |
| `key:KEY` | Press a key: `Tab`, `Enter`, `Escape`, `Up`, `Ctrl+L`, `h`, ... |
| `type:TEXT` | Type text |
| `sleep:MS` | Wait |
| `resize:COLSxROWS` | Resize the terminal |
| `shot:NAME` | Only capture the screen |

`--live` adds automations that dispatch the fake agent (a success, a failure, and an agent that
writes straight to the terminal). Sessions start under the automation's name (`qa-ok`) and take
the title the fake agent gives them a few seconds later, as OpenCode does. `--config PATH` uses a real settings file instead of the
sandbox: its automations run real agents.
