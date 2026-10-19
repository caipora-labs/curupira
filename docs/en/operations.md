# Running Curupira

All commands read the same configuration file and use the same dispatch pipeline. The
short alias `curu` accepts every command.

## Commands { #commands }

| Command | What it does |
| --- | --- |
| `curupira validate` | Checks the TOML, references, plugins, and prompts. Runs no automation and writes no state. |
| `curupira run` | Runs the tasks that are available now, then exits. |
| `curupira run --size N` | Same, but admits at most `N` tasks. |
| `curupira run --dry-run` | Prints the first task that would run and its rendered prompt. Clones nothing, starts no agent. |
| `curupira run --watch` | Keeps polling and running tasks until interrupted. |
| `curupira tui` | The continuous loop, behind the interactive [terminal dashboard](tui.md). |
| `curupira plugins …` | Lists and inspects the available [plugins and triggers](extensions.md#manage). |

`--dry-run`, `--watch`, and `--size` cannot be combined; Curupira exits with status `2`
if you try.

Global options go before the command:

```sh
curupira --config ./settings-dev.toml validate
curupira --config ./settings-dev.toml run --watch
curupira --log-level DEBUG run --watch
curupira --version
```

`--config` defaults to `~/.curupira/settings.toml`. `--log-level` overrides
`[settings].log_level` for one process (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).

## Output { #output }

`run` prints one line per finished task, separated by a tab:

```text
ok      resolve-ready-issues:acme/api:plugins-py/github-issues:9c1e…
fail    review-ready-prs:acme/api:plugins-py/github-pull-requests:41ad…  agent exited 1: …
```

The second column is the task identity: automation, repository, trigger, and a hash of
the item's fields. `ok` lines go to stdout and `fail` lines to stderr, so you can pipe
them separately.

`run --dry-run` prints the identity and the exact prompt the agent would receive:

```text
dry-run resolve-ready-issues:acme/api:plugins-py/github-issues:9c1e…
--- prompt ---
Resolve issue #128: Retry flaky webhook deliveries
…
--- end prompt ---
```

## Exit codes { #exit-codes }

| Code | Meaning |
| --- | --- |
| `0` | Success. For `run`, every executed task finished `ok`. |
| `1` | At least one task failed, or a plugin or runtime error stopped the run. |
| `2` | Configuration error (invalid TOML, unknown reference, conflicting flags). |
| `130` | Interrupted with ++ctrl+c++. |

## Scheduling { #scheduling }

- Up to `[settings].max_active_tasks` tasks run at the same time (default `1`).
- In `--watch` mode, Curupira polls every automation each
  `[settings.polling].poll_interval_seconds` (default `30`).
- A task that finished `ok` is remembered in the state database and never runs again.
- A task that fails is not retried in the same process. The next `run` (or a restarted
  `--watch`) tries it again.
- Each agent run is limited to `[settings].task_timeout_minutes` (default `20`).

## One process at a time { #lock }

`run` and `tui` hold `~/.curupira/dispatch.lock` while they work. A second process that
tries to dispatch fails fast instead of racing the first. `validate`, `run --dry-run`, and
`plugins` do not take the lock.

## Resuming sessions { #resume }

When an agent announces a session id (or Curupira assigns one), it is saved with the task.
If the process stops before the task finishes, the next run resumes that session and asks
the agent to continue the previous work instead of starting over. The session is removed
when the task finishes `ok`.

## Changing the configuration { #reload }

Curupira reads the configuration once when a command starts. After editing
`settings.toml`, run `curupira validate`, then restart `run --watch` or `tui` to pick up
the change. Running tasks finish with the settings they started with.
