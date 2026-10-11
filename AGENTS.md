# AGENTS.md

Instructions for coding agents. Humans start at [CONTRIBUTING.md](CONTRIBUTING.md).
A task or prompt overrides this file.

## Project

Curupira (Caipora Labs) runs local automations for developers. Each TOML automation
watches one source — GitHub issues or pull requests, Azure DevOps pull requests,
Trello cards, monday.com items, or cron — and sends its prompt to a coding-agent CLI
already installed on the machine (OpenCode, Codex, Claude Code, Cursor, Gemini CLI,
GitHub Copilot CLI, Kilo CLI, pi, or Qwen Code).

The package, import, and console script are `curupira`; `curu` is the same entry
point (`curupira.cli:main`, also `python -m curupira`). Pure Python 3.11–3.14 on
Linux, macOS, and Windows. The only supported programmatic export is
`curupira.__version__`. Third-party plugins import only `curupira.plugins`. Curupira
does not authenticate; provider CLIs and the user environment do.

Default settings are `~/.curupira/settings.toml`. `validate` checks configuration
only. `run` drains available tasks; `run --watch` and `tui` poll until interrupted.
One process holds `~/.curupira/dispatch.lock`.

## Architecture

Implementations depend on the contract in each `base.py`, not on sibling packages.

- **Pipeline.** `config.py` loads one frozen `ApplicationSettings`.
  `dispatcher.create_task_feeds` builds a `TaskFeed` per automation from the trigger
  registry. `scheduler.TaskScheduler` admits work up to `max_active_tasks`.
  `executor.TaskExecutor` checks out the repo, renders `${name}` placeholders, and
  calls the adapter. The default `checkout` is `worktree` (a task branch from the
  fetched remote default branch). `checkout = "main"` means the shared checkout, not
  a branch named `main`, and does not fetch or switch branches.
- **Processes.** Headless runs start only through `AsyncProcessRunner`
  (`clients/process.py`): an argument vector, a timeout, and bounded output. No shell
  string. The TUI assistant (`Ctrl+G`) is the other starter: it mounts a verified
  `InteractiveLaunchSpec` in `PtyTerminal` via `pty.fork` and `os.execvp`. Do not add
  a third. On Windows, `PtyTerminal` shows a placeholder and does not spawn.
- **Providers.** Built-ins are `providers/<name>/provider.py`, registered with the
  Pluggy hooks in `hooks.py` and listed in `manager.py`. A provider may contribute
  triggers, coding-agent adapters, or both. Third-party code uses entry points
  `curupira.triggers` and `curupira.agents`. `PLUGIN_API_VERSION` is `2`. Add a
  method with a default instead of bumping it.
- **Models.** Configuration extends `ValidatedModel` (frozen, `extra="forbid"`).
  `parse_cli_profile` and `parse_automation_configuration` validate with the
  registered model. Each profile or trigger sets `provider` or `trigger_type` to
  a `Literal` default equal to its registered name. Do not replace `CliProfile`
  or `AutomationConfiguration` with a closed union. External CLI JSON ignores
  unknown fields. Put a shared constraint once, as an `Annotated` alias in
  `models/base.py`.
- **Agents.** Adapters implement `build_arguments` and return argv. Set `auto_model`,
  or override `interactive_launch`, only when that CLI's official docs confirm the
  flag; cite the URL on the override. Otherwise leave `interactive_launch` returning
  `None` and do not invent `--model auto`. `curupira.tasks.<name>` and
  `curupira.agents.<name>` stay importable.
- **Failures.** Expected failures subclass `DispatchError`. Retry only
  `TransientCliError` and `TransientHttpApiError`, using the existing `pyresilience`
  `RetryConfig` on the GitHub and Azure clients. Do not retry authentication,
  configuration, or agent-task failures. Log with `logging.getLogger(__name__)`.

## Repository map

| Path | Look here when |
| --- | --- |
| `src/curupira/cli.py` | Subcommands, exit codes, the dispatch lock. |
| `src/curupira/config.py`, `config_reload.py` | TOML load and resolve; reload after in-flight tasks drain. |
| `src/curupira/models/` | Pydantic contracts. Shared validators are in `models/base.py`. |
| `src/curupira/tasks/` | `Trigger`, `TaskSource`, `TaskFeed`, registry, revalidation. |
| `src/curupira/dispatcher.py`, `scheduler.py`, `executor.py` | Dispatch, concurrency, checkout, and the agent lifecycle. |
| `src/curupira/agents/` | Adapter contract, registry, `create_cli_adapter`, assistant model resolution. |
| `src/curupira/providers/<name>/` | One built-in integration. Register it in `manager.py`. |
| `src/curupira/plugins.py` | The only module plugins may import. |
| `src/curupira/clients/` | GitHub GraphQL and `gh` token, `az`, Trello, monday.com, process runner. |
| `src/curupira/vcs/` | Clone and worktrees (`VersionControl`, `git_cli.py`). |
| `src/curupira/storage/` | SQLite sessions, completed-task fingerprints, and cron state. |
| `src/curupira/tui/` | Textual dashboard. `assistant_panel.py` mounts `PtyTerminal`. |
| `src/curupira/runtime.py`, `telemetry.py` | `~/.curupira` paths and optional OTLP/HTTP spans. |
| `tests/` | Mirrors `src/`. Fakes: `tests/fakes.py`. Builders: `tests/helpers.py`. |
| `tests/providers/<name>/`, `tests/plugins/` | Provider tests, and in-process entry-point fixtures. |
| `curupira.example.toml` | Example config. `validate` must keep accepting it. |
| `docs/en/` | Canonical docs. `docs/pt/` and `docs/es/` are translations. |
| `main.py`, `mkdocs.yml` | Docs macros. Provider, trigger, and install tables come from the registries. |
| `scripts/` | Packaging guard, install smoke, release CI check. Not the application. |

A new built-in provider needs `providers/<name>/`, a `manager.py` entry, and
`tests/providers/<name>/`. A coding-agent provider also needs
`docs/en/providers/<name>.md` and one alphabetical `mkdocs.yml` nav line. Do not
hand-edit the generated registry tables. Steps: [CONTRIBUTING.md](CONTRIBUTING.md).

## Always

- Match the nearest implementation and its tests before adding a helper or layer.
- Cover every behavior change with a test. For a bug, add a test that fails first when that is practical.
- Reuse `AsyncProcessRunner`, `ValidatedModel`, `PollingTaskFeed`, the registries, and `pyresilience`.
- Type every function. Pyrefly is strict. Avoid `Any` in `src/` (tests already ignore `ANN401`).
- Give public modules, classes, and functions Google-style docstrings. Profile fields use `Field(description=...)` and no `Attributes:` block. Other models list fields under `Attributes:`. Mark overrides with `@override`.
- Update `CHANGELOG.md` (`Unreleased`) and `docs/en/` when behavior, commands, configuration, or public docs change. Update this file when these instructions change.

## Never

- Start a headless subprocess outside `AsyncProcessRunner`, or pass a shell string.
- Interpolate user input into SQL. Bind every value; identifiers are private constants.
- Allow `..` or an absolute path in `setup_script`. GitHub `repo` must not contain `.` or `..` segments.
- Commit, log, or echo secrets. Tests must not hit the network or call real `gh`, `az`, Trello, monday.com, or coding-agent CLIs.
- Hand-edit `uv.lock`. After a justified `pyproject.toml` change, run `uv lock`. Do not bump `src/curupira/_version.py` or push tags.
- Add or upgrade dependencies, edit `.github/workflows/`, or break the TOML schema or CLI unless the task asks for that.
- Add a blanket `# noqa` or `# type: ignore`. Scope one rule, justify it, or fix the code. Do not weaken Ruff, Pyrefly, or the 85% branch-coverage floor.
- Treat a lint or test failure as pre-existing without checking `main`.
- Edit `docs/pt/` or `docs/es/` in the feature change. Change `docs/en/`; translations are a follow-up.
- Invent interactive CLI flags, or duplicate a feed, adapter, or client that already exists.
- Refactor unrelated code in a focused change.

## Workflow

From the repository root, after `uv sync --dev`:

```bash
uv run --no-sync pytest tests/test_cli.py -k example   # nearest file or test
uv run --no-sync pytest                                 # full suite
uv run --no-sync pytest --cov                           # branch coverage, fail under 85%
uv run --no-sync ruff check .                           # lint; --fix for safe fixes only
uv run --no-sync ruff format --check .
uv run --no-sync pyrefly check
uv run --no-sync curupira --config curupira.example.toml validate
```

Run the nearest test while iterating. Before a pull request, run the full suite,
Ruff, Pyrefly, and example-config validate. CI on Ubuntu runs Ruff and Pyrefly on
Python 3.11, and pytest plus validate on 3.11–3.14 (`uv sync --frozen --dev`).
That pytest has no `--cov`, so run coverage locally when behavior changes.
`prek` (`.pre-commit-config.yaml`) runs Ruff and Pyrefly through `uv run --no-sync`;
install with `uv run --no-sync prek install`. Pytest uses `asyncio_mode = auto`
and treats warnings as errors.

When `docs/en/` changes: `uv run --group docs mkdocs build --strict`. Packaging
(`scripts/check_packaged_readme.py`) and `uv run pip-audit` are for release-level
changes; see [CONTRIBUTING.md](CONTRIBUTING.md).

## Testing

- Place tests next to the code: `tests/test_<module>.py`, `tests/<package>/`, or `tests/providers/<name>/`.
- Use `tests/fakes.py` and `tests/helpers.py`. Assert observable behavior, including error paths.
- `@pytest.mark.parametrize` is the usual way to cover variants. Add a case only when it exercises this change, and only if an existing test does not already cover it.
- `test_example_configuration_is_valid` must stay green when `curupira.example.toml` changes.

## Making a change

1. Read the implementation and the tests that already cover it.
2. Make the smallest change. Preserve CLI behavior, TOML fields, and plugin imports unless the task says otherwise.
3. Add or update tests and, when the behavior is user-visible, `docs/en/` and `CHANGELOG.md`.
4. Run the nearest tests, then the broader checks. Read the diff.
5. Summarize what changed and any check you did not run.

A new dependency needs a reason the standard library and the current dependencies cannot do the job, plus an explicit request. Open the pull request from `main` with [.github/PULL_REQUEST_TEMPLATE.md](.github/PULL_REQUEST_TEMPLATE.md).

## Details

- [CONTRIBUTING.md](CONTRIBUTING.md) — setup, packaging, adding a provider, translations, releases, PtyTerminal limits.
- [docs/en/plugins.md](docs/en/plugins.md) — third-party triggers and agents.
- [docs/en/automations.md](docs/en/automations.md) — trigger reference.
- [README.md](README.md) — product behavior, configuration, and commands.
