# Terminal dashboard

`curupira tui` (or `curu tui`) runs the same continuous dispatch loop as
`curupira run --watch`, started from the dashboard entry point.

```sh
curupira tui
```

## What it does today { #status-mode }

The Rust CLI runs the dashboard in **status mode**:

- It prints `TUI: running dispatch dashboard (status mode); press Ctrl+C to stop` on stderr.
- It polls every automation and runs tasks exactly like `run --watch`, printing `ok` and
  `fail` lines as tasks finish.
- It takes `~/.curupira/dispatch.lock`, so it cannot run next to another `run` or `tui`.
- ++ctrl+c++ stops admitting work and exits with status `130`.

Everything on [Running Curupira](operations.md) about polling, concurrency, and exit
codes applies to `tui` as well.

!!! note "Interactive panels are not available yet"
    The dashboard has no panels or assistant yet. Until it does, `run --watch` and `tui`
    behave the same.

## The `[assistant]` table { #assistant }

`[assistant]` is reserved for the interactive assistant. Curupira already reads and
validates it, so a file written today keeps working when the panel arrives:

```toml
[assistant]
agent = "claude"   # a built-in provider name, checked by `curupira validate`
model = "sonnet"   # optional
```

An unknown `agent` is a configuration error. See
[Configuration](configuration.md#assistant) for the field reference.
