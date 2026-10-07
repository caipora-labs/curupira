# Operations

All commands use the same configuration file and execution pipeline.

```bash
curupi validate
curupi run
curupi run --dry-run
curupi watch
curupi batch [--size N]
```

- `validate` checks TOML and references without running an automation, calling external CLIs, or writing state. It exits `0` for valid configuration and `2` for configuration errors.
- `run` executes one currently available task and waits for the agent. It returns the agent's status, `0` when no task is available, and `1` on dispatch errors.
- `run --dry-run` previews selection without reserving or persisting cron occurrences, checking out a repository, or executing.
- `watch` polls all automations continuously until interrupted. It exits `1` if an executed task failed, otherwise `0`.
- `batch` drains currently available tasks; `--size N` limits the number.

Select another TOML by placing the option before the command:

```bash
curupi --config ./settings-dev.toml validate
curupi --config ./settings-dev.toml watch
```

`run` and `watch` append task records to `~/.curupi/logs/curupi.log`. Sessions interrupted by process restarts are stored in the state database; `watch` resumes saved sessions after restart. Transient `gh` failures retry with backoff. Authentication, configuration, output-format, and agent-task failures are not automatically retried.
