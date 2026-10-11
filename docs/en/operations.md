# Operations

All commands use the same configuration file and execution pipeline. The short alias `curu` accepts the same commands.

```bash
curupira validate
curupira run
curupira run --dry-run
curupira run --size N
curupira run --watch
curupira tui
```

- `validate` checks TOML and references without running an automation, calling external CLIs, or writing state. It exits `0` for valid configuration and `2` for configuration errors.
- `run` drains currently available automation tasks through the shared scheduler. It exits `1` if an executed task failed, otherwise `0`.
- `run --size N` limits a finite drain to at most N tasks.
- `run --dry-run` previews one selected task without reserving or persisting cron occurrences, checking out a repository, or executing.
- `run --watch` polls all automations continuously until interrupted. It exits `1` if an executed task failed, otherwise `0`.
- `tui` runs the same continuous scheduler as `run --watch` inside an interactive Textual dashboard (metrics, active agents, and logs). Shortcuts: `Ctrl+G` open/close the [embedded assistant](assistant.md) side panel, `F1` help, `F2` pause/resume admissions, `F3` config summary, `F5` refresh metrics, `Ctrl+C` quit.
- The dashboard hosts the assistant in a half-width side panel backed by the reusable
  `PtyTerminal` widget (`curupira.tui.pty_terminal.PtyTerminal`). Platform support in
  v1: Linux and macOS; Windows shows an unsupported placeholder. Emulation uses `pyte`
  (LGPL-3.0) as a dynamic dependency. See [TUI assistant](assistant.md) for the
  Ctrl+G workflow and CONTRIBUTING.md for PTY throughput tables and lifecycle caveats.

While `run --watch` or `tui` is running, editing the configuration file hot-reloads settings without restarting the process. New work stops being admitted as soon as the file changes; tasks that are already running keep their resolved snapshots and finish. After every in-flight task completes, Curupira reloads the TOML, rebuilds discovery feeds, and resumes polling with the latest configuration. If the updated file is invalid, admission stays paused until a valid configuration is saved.

Select another TOML by placing the option before the command:

```bash
curupira --config ./settings-dev.toml validate
curupira --config ./settings-dev.toml run --watch
```

`run` and `run --watch` append task records to `~/.curupira/logs/curupira.log`. Sessions interrupted by process restarts are stored in the state database; `run --watch` resumes saved sessions after restart. Transient `gh` failures retry with backoff. Authentication, configuration, output-format, and agent-task failures are not automatically retried.
