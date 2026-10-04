# gh-dispatch

Dispatch GitHub issues, pull requests, and cron occurrences to local AI coding-agent
CLIs with bounded concurrency and exclusive execution per checkout.

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
uv tool install gh-dispatch
```

Or with pipx:

```bash
pipx install gh-dispatch
```

## Configuration

The default settings file is `~/.gh-dispatch/settings.toml`. Initialize it by copying
the example and adjust repositories, paths, queries, and prompts:

```bash
mkdir -p ~/.gh-dispatch
cp gh-dispatch.example.toml ~/.gh-dispatch/settings.toml
```

The `~/.gh-dispatch` directory is created automatically when the default file is first
loaded. Pass `--config path/to/settings.toml` to use a different file; relative workspace,
state, and automation paths are resolved from that file's directory.

```toml
[settings]
max_active_tasks = 1
workspace_dir = "~/.gh-dispatch/workspaces"
state_db_path = "~/.gh-dispatch/state.sqlite3"
# Endpoint opcional de traces OTLP/HTTP; omita para desativar a telemetria.
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

`model`, `effort`, and `agent` are optional on every profile and their flags are omitted
when unconfigured. A profile is provider-specific configuration; it never defines a
custom agent. Custom-agent selection only uses a provider's verified native flag:

| Provider   | Custom agent (`agent`) | Model (`model`)      | Effort (`effort`)              |
| ---------- | ---------------------- | -------------------- | ------------------------------ |
| `opencode` | Optional `--agent`     | Optional `--model`   | Optional `--variant`           |
| `claude`   | Optional `--agent`     | Optional `--model`   | Optional `--effort`            |
| `codex`    | Not supported; rejected | Optional `--model`  | Optional reasoning effort      |
| `cursor`   | Not supported; rejected | Optional `--model`  | Not supported; rejected        |

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

`max_active_tasks` bounds concurrently running coding agents (default 1). Checkouts are
exclusive: tasks sharing a workspace path run serially while unrelated workspaces run
concurrently. Checkouts are created on demand with `gh repo clone` under
`workspace_dir/owner/repo`. Nothing creates branches or worktrees, and nothing modifies
issues or pull requests.

Each cron automation coalesces overdue ticks into a single pending occurrence; the same
automation never runs concurrently with itself. `schedule` is a five-field cron
expression, `timezone` is IANA (defaulting to `coding_agents.defaults.timezone`), and
`start_date`/`end_date` form an optional inclusive window interpreted in that timezone.
Without `start_date`, the window starts when the automation is first recorded.

### OpenTelemetry

Defina `settings.otlp_endpoint` com o endpoint OTLP/HTTP de traces (por exemplo,
`http://localhost:4318/v1/traces`) para exportar um span por issue, pull request ou
ocorrência cron despachada. Cada span inclui repositório, tipo, identificador e resultado
(sucesso ou falha); falhas também incluem `error.message`. O endpoint deve aceitar
OTLP sobre HTTP/protobuf. Se o campo for omitido, nenhuma telemetria será exportada.

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

### Arquivo de logs

Os comandos `run` e `watch` acrescentam registros a
`~/.gh-dispatch/logs/gh-dispatch.log`; reiniciar o processo não apaga o conteúdo anterior.
Cada tarefa registra início e conclusão com horário, repositório, tipo e identificador. Se
a tarefa falhar, o registro inclui o erro.

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
`run --dry-run` never reserves or persists cron occurrences.

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
uv run pytest --cov --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run pyrefly check
uv build
uv run twine check dist/*
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for environment setup and the exact verification
commands, and [CHANGELOG.md](CHANGELOG.md) for release notes.

## License

MIT — see [LICENSE](LICENSE).
