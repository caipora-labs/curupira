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
- `tui` runs the same continuous scheduler as `run --watch` inside an interactive Textual dashboard (metrics, active agents, and logs). Shortcuts: `F1` help, `F2` pause/resume admissions, `F3` config summary, `F5` refresh metrics, `Ctrl+C` quit.
- The dashboard package also exposes a reusable `PtyTerminal` widget
  (`curupira.tui.pty_terminal.PtyTerminal`) for embedding an interactive PTY child
  (building block for a future side-panel coding assistant). It is not mounted in the
  orchestrator layout or configured via TOML yet. Platform support in v1: Linux and
  macOS; Windows shows an unsupported placeholder. Emulation uses `pyte` (LGPL-3.0) as
  a dynamic dependency. The reader feeds pyte in 256-byte slices under a 5 ms budget;
  rendering coalesces styles, refreshes dirty rows at ~30 fps, and avoids
  `HistoryScreen`'s per-event wrapper. Reproduced on Linux 6.12.94+ (x86_64, 4× Xeon
  CPUs, 15 GiB RAM, Python 3.11.17) with Textual `run_test` `(120, 40)`, 20 s sample,
  1 ms ticker via `scripts/measure_pty_throughput.py`: `yes | head -c 50M` 0.386 MB/s
  (loop p50/p99/max 10.9/16.1/26.5 ms), `seq 2000000` 0.579 MB/s (10.6/19.5/30.7 ms),
  `cat` of 40 MiB 0.904 MB/s (10.4/47.1/80.3 ms). See CONTRIBUTING.md for lifecycle
  caveats (host `SIGKILL`, `setsid` grandchildren, blocking shutdown grace, write
  backpressure).

While `run --watch` or `tui` is running, editing the configuration file hot-reloads settings without restarting the process. New work stops being admitted as soon as the file changes; tasks that are already running keep their resolved snapshots and finish. After every in-flight task completes, Curupira reloads the TOML, rebuilds discovery feeds, and resumes polling with the latest configuration. If the updated file is invalid, admission stays paused until a valid configuration is saved.

Select another TOML by placing the option before the command:

```bash
curupira --config ./settings-dev.toml validate
curupira --config ./settings-dev.toml run --watch
```

`run` and `run --watch` append task records to `~/.curupira/logs/curupira.log`. Sessions interrupted by process restarts are stored in the state database; `run --watch` resumes saved sessions after restart. Transient `gh` failures retry with backoff. Authentication, configuration, output-format, and agent-task failures are not automatically retried.
