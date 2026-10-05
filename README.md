# gh-dispatch

gh-dispatch runs automations on your machine. It takes a GitHub issue or pull request, or a local cron occurrence, and hands it to a coding-agent CLI you already have.

Each automation in the settings TOML watches one source (issues, pull requests, or a
cron schedule) and carries its own prompt. All automations share one discovery,
scheduling, and execution pipeline: `run` executes a single currently available task,
while `watch` polls every automation continuously.

## Requirements

- Python 3.11 or newer (3.11–3.14 supported; Linux, macOS, and Windows)
- [`gh`](https://cli.github.com/) installed and authenticated (`gh auth login`)
- Only the CLIs used by the configured profiles need to be installed:
  [`opencode`](https://opencode.ai/), [`codex`](https://developers.openai.com/codex/cli/),
  [`claude`](https://code.claude.com/docs/en/cli-reference), or the Cursor CLI (`agent`)

## Installation

Install as an isolated tool:

```bash
uv tool install git+https://github.com/mariotaddeucci/gh-dispatch.git
```

The package is not yet published to PyPI. Install it directly from GitHub with `uv` as
shown above.

## Documentation

See the [full guide in Portuguese](https://mariotaddeucci.github.io/gh-dispatch/) for
installation, automation configuration, providers, and operational commands.

## Configuration

The default settings file is `~/.gh-dispatch/settings.toml`. Download the example
configuration directly to that location, then adjust repositories, paths, queries, and
prompts:

```bash
mkdir -p ~/.gh-dispatch
curl -fsSL https://raw.githubusercontent.com/mariotaddeucci/gh-dispatch/main/gh-dispatch.example.toml \
  -o ~/.gh-dispatch/settings.toml
```

The `~/.gh-dispatch` directory is created automatically when the default file is first
loaded. Pass `--config path/to/settings.toml` to use a different file; relative workspace,
state, and automation paths are resolved from that file's directory.

```toml
[settings]
max_active_tasks = 1
workspace_dir = "~/.gh-dispatch/workspaces"
state_db_path = "~/.gh-dispatch/state.sqlite3"
# Optional OTLP/HTTP trace endpoint; omit it to disable telemetry.
# otlp_endpoint = "http://localhost:4318/v1/traces"

[settings.polling]
poll_interval_seconds = 30
batch_size = 100
cron_poll_interval_seconds = 1

[coding_agents.defaults]
profile = "opencode-default"
timezone = "UTC"

[coding_agents.profiles.opencode-default]
provider = "opencode"

[coding_agents.automations.resolve-ready-issues]
trigger_type = "issue"
repo = "acme/api"
query = "is:open label:agent-ready sort:created-asc"
prompt = "Resolve issue ${issue_number}: ${issue_title}\n\n${issue_body}"
```

### Automations

`[coding_agents.automations.<name>]` is a keyed map; the map key is the automation ID
and is carried into every task identity. `trigger_type` selects the source:

- `"issue"` — discovers matching issues with `query`
- `"pull_request"` — discovers matching pull requests with `query`
- `"cron"` — produces occurrences from `schedule` instead of querying GitHub

Every automation requires `repo`, `prompt`, and — depending on the trigger — `query`
or `schedule`. Optional `profile` selects a named CLI profile; otherwise the default
profile applies. Optional `path` pins the automation to an existing checkout or an
alternative clone destination; relative paths resolve from the TOML directory, as do
`workspace_dir` and `state_db_path`. Different repositories cannot share one workspace
path. Automations keep file order, and one-shot selection follows that order.

### Providers and native options

`model`, `effort`, and `agent` are optional and their flags are omitted when unconfigured.
`agent` uses the provider's native setting: it selects a custom agent in OpenCode and
Claude Code, a named Codex CLI profile, and Cursor's execution mode.

| Provider   | `agent` mapping                | `model`            | `effort`                                |
| ---------- | ------------------------------ | ------------------ | --------------------------------------- |
| `opencode` | Custom agent via `--agent`     | Optional `--model` | Optional `--variant`                   |
| `claude`   | Custom agent via `--agent`     | Optional `--model` | Optional `--effort`                    |
| `codex`    | Config profile via `--profile` | Optional `--model` | `model_reasoning_effort` via `--config` |
| `cursor`   | Mode via `--mode`              | Optional `--model` | Not supported; rejected                |

Cursor `agent` accepts `agent`, `ask`, or `plan` as the value of `--mode`.

OpenCode runs `opencode run --format json`; a saved session resumes with `--session`.
Codex runs `codex exec --json`, resumes with `codex exec resume <thread_id>`, maps
`agent` to `--profile`, and maps `effort` to `--config model_reasoning_effort=<level>`.
Codex effort levels include `low`, `medium`, `high`, `xhigh`, `max`, and `ultra`; which
levels are available depends on the selected model and CLI version. Claude Code runs
`claude -p --output-format stream-json --verbose`, resumes with `--resume`, and passes
`agent` and `effort` through their native flags. Cursor runs `agent --print
--output-format stream-json`, resumes with `--resume`, and maps `agent` to `--mode`; it
does not accept `effort`.

Explicit permission overrides are also provider-specific (`auto_approve` for OpenCode,
`sandbox`/`auto_review` for Codex, `permission_mode`/`permission_prompts` for Claude
Code, `force`/`trust` for Cursor). When omitted, each CLI keeps its native policy.

### Prompts and placeholders

Placeholders use `${name}` syntax and are validated when the configuration loads.
Common fields: `${repo}`, `${automation_id}`, `${task_type}`, `${task_number}`,
`${task_title}`, `${task_body}`, `${task_url}`. Issues add `${issue_number}`,
`${issue_title}`, `${issue_body}`, `${issue_url}`. Pull requests add
`${pull_request_number}`, `${pull_request_title}`, `${pull_request_body}`,
`${pull_request_url}`, `${pull_request_is_draft}`, `${pull_request_head_ref}`, and
`${pull_request_base_ref}`. For cron tasks, `${task_number}` is the occurrence timestamp.

### Discovery, concurrency, and cron semantics

Queries use GitHub search syntax and fetch up to `batch_size` items per poll (default
100, up to 1000). When a full cycle finds nothing, the shared poller waits
`poll_interval_seconds` (default 30s); consecutive empty cycles double the wait up to
5 minutes, and any discovery resets it. Each automation deduplicates its own items, so
two automations may process the same issue with different prompts.

Polls that use the `project:` search qualifier keep the `open` state and filter board
items to the `Todo` status automatically.

`max_active_tasks` bounds concurrently running coding agents (default 1). By default,
each task runs in a new worktree beside its base checkout, so tasks for the same repository
can run concurrently without sharing edits. The worktree branch is created from the
fetched remote default branch and is not pushed. Set `checkout = "main"` to use the
shared checkout instead (this means the shared checkout, not a branch named `main`, and
restores the previous exclusive behavior). `path` continues to select the base checkout.
Checkouts are created on demand with `gh repo clone` under `workspace_dir/owner/repo`.
Nothing modifies issues or pull requests.

An optional `setup_script` is a repository-relative executable path (no absolute paths
or `..`). It runs directly, with the checkout root as its working directory, only when
the base checkout has just been cloned. It does not run for an existing checkout or in
the task worktree, so files or dependencies installed there are not available to the
agent. Use `checkout = "main"` when the agent must run where setup wrote files. A nonzero
setup exit prevents the agent from starting; the newly cloned checkout is removed, while
an existing checkout is preserved. `validate` checks the path syntax but does not require
the script to exist. `run --dry-run` does not fetch, clone, create a worktree, or run setup,
so it cannot verify that the script or worktree will work. Existing automation TOML remains
valid, but now uses a worktree by default; configure `checkout = "main"` to keep the old
shared-checkout behavior.

Each cron automation coalesces overdue ticks into a single pending occurrence; the same
automation never runs concurrently with itself. `schedule` is a five-field cron
expression, `timezone` is IANA (defaulting to `coding_agents.defaults.timezone`), and
`start_date`/`end_date` form an optional inclusive window interpreted in that timezone.
Without `start_date`, the window starts when the automation is first recorded.

### OpenTelemetry

Set `settings.otlp_endpoint` to an OTLP/HTTP trace endpoint (for example,
`http://localhost:4318/v1/traces`) to export one span for each dispatched issue, pull
request, or cron occurrence. Each span includes the repository, type, identifier, and
result (success or failure); failures also include `error.message`. The endpoint must
accept OTLP over HTTP/protobuf. If the field is omitted, no telemetry is exported.

### State files

Running sessions and cron schedule state live in `state_db_path` (default
`~/.gh-dispatch/state.sqlite3`). The per-user dispatch lock is stored in
`~/.gh-dispatch/dispatch.lock`, and the dedicated log directory is
`~/.gh-dispatch/logs`. Only one `run` or `watch` process can dispatch at a time; a second
process exits with an error rather than running tasks in parallel. Session records are
removed when the agent process ends; `watch` resumes all saved sessions after a restart,
and `run` resumes the saved session of the task it selects. If the file exists but is not
a compatible database, the application exits with an error instead of deleting it —
delete or move the file yourself to start fresh.

### Log file

The `run` and `watch` commands append records to
`~/.gh-dispatch/logs/gh-dispatch.log`; restarting the process does not erase existing
content. Each task records its start and completion time, repository, type, and
identifier. If a task fails, the record includes the error.

## Usage

Validate configuration without calling external CLIs or writing state:

```bash
gh-dispatch validate
```

Execute one currently available task and wait for the agent to finish:

```bash
gh-dispatch run
```

Preview the selected task without reserving, persisting, cloning, or executing:

```bash
gh-dispatch run --dry-run
```

Poll all automations with the shared bounded scheduler until interrupted:

```bash
gh-dispatch watch
```

`validate` exits `0` when the configuration is valid and `2` on configuration errors.
`run` exits with the agent process status, `0` when no task is available, and `1` on
dispatch errors. `watch` exits `1` when any executed task failed, otherwise `0`.
`run --dry-run` never reserves or persists cron occurrences and does not perform checkout,
worktree, or setup operations.

`watch` runs every CLI non-interactively so concurrent workers never contend for the
terminal UI. Transient `gh` failures are retried with backoff; authentication,
configuration, output-format, and agent-task failures are not retried automatically.

## Public interface

`gh-dispatch` is CLI-first. The only supported programmatic surface is
`gh_dispatch.__version__`; all other modules are internal implementation details that
may change without notice.

## Development and validation

```bash
uv sync --dev
uv run --no-sync pytest
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pyrefly check
uv build
uv run --no-sync twine check dist/*
```

To inspect branch coverage locally, run `uv run --no-sync pytest --cov --cov-report=term-missing`;
the configured minimum is 85%.

See [CONTRIBUTING.md](CONTRIBUTING.md) for environment setup and the exact verification
commands, and [CHANGELOG.md](CHANGELOG.md) for release notes.

## License

MIT — see [LICENSE](LICENSE).
