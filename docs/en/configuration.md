# Configuration

Curupira reads one TOML file, `~/.curupira/settings.toml` by default (`--config` picks
another). It has six kinds of tables:

| Table | What it declares |
| --- | --- |
| `[settings]` | Runtime limits, paths, and polling |
| `[environment]` | Variables copied into every process Curupira starts |
| `[repositories.<alias>]` | Git remotes the agents work in |
| `[agents]` | The default profile and one table per agent profile |
| `[plugins.<alias>]` | Task-source packages and how to launch them |
| `[automations.<name>]` | What to watch, where to work, which agent, and the prompt |

The names after the dot (`api`, `claude`, `plugins-py`, `resolve-ready-issues`) are yours
to choose. Run `curupira validate` after every change.

## A complete file { #example }

```toml
[settings]
max_active_tasks = 1
workspace_dir = "~/.curupira/workspaces"
state_db_path = "~/.curupira/state.sqlite3"
log_level = "INFO"
task_timeout_minutes = 20

[settings.polling]
poll_interval_seconds = 30
batch_size = 100

[environment.vars]
# HTTPS_PROXY = "http://proxy.internal:8080"

[repositories.api]
remote = "https://github.com/acme/api.git"
# path = "~/code/api"
# setup_script = "scripts/bootstrap.sh"

[agents.defaults]
profile = "opencode-default"
timezone = "UTC"

[agents.profiles.opencode-default]
provider = "opencode"

[plugins.plugins-py]
type = "uvx"
args = ["--from", "curupira-plugins", "curupira-plugins"]
tools = ["*"]

[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
linked_pull_request = false
prompt = "Resolve issue ${issue_number}: ${issue_title}\n\n${issue_body}"
```

## Settings { #settings }

Every key is optional.

| Key | Default | Meaning |
| --- | --- | --- |
| `max_active_tasks` | `1` | Agents that may run at the same time. |
| `workspace_dir` | `~/.curupira/workspaces` | Where repositories are cloned. |
| `state_db_path` | `~/.curupira/state.sqlite3` | Completed tasks, cron occurrences, and resumable sessions. |
| `log_level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. `--log-level` overrides it. |
| `task_timeout_minutes` | `20` | Deadline for one agent run, and for `setup_script`. |
| `max_output_bytes` | `1000000` | Output kept from each agent run and setup script. |
| `polling.poll_interval_seconds` | `30` | Pause between polls in `run --watch` and `tui`. |
| `polling.batch_size` | `100` | Items requested from each trigger per poll. |

Relative paths are resolved against the directory of the settings file.

## Environment { #environment }

Every process Curupira starts — coding agents, Git, `setup_script`, and extensions — receives a copy of every environment variable the Curupira process can see. `[environment.vars]` replaces those values. Omit the table to pass the process environment through unchanged.

Values are literal strings. `$VAR` and `${VAR}` are not expanded.

Curupira still sets the working directory (`PWD`) and removes repository-binding variables (`GIT_DIR` and the other `GIT_*` bindings) after these overwrites, and a coding agent's own variables (for example `OPENCODE_DB`) are applied after `[environment.vars]`.

```toml
[environment.vars]
HTTPS_PROXY = "http://proxy.internal:8080"
GITHUB_TOKEN = "ghp_..."
```

| Key | Meaning |
| --- | --- |
| `vars` | Environment variable names and the values that replace them. Empty when omitted. Names match `[A-Za-z_][A-Za-z0-9_]*`. |

## Repositories { #repositories }

`[repositories.<alias>]` is a Git checkout that one or more automations work in.

| Key | Required | Meaning |
| --- | --- | --- |
| `remote` | yes | The URL for `git clone`: HTTPS, SSH, or `user@host:path`. |
| `path` | no | Use or create the checkout here instead of `workspace_dir/<alias>`. |
| `setup_script` | no | A repository-relative executable run once, right after a fresh clone. |

The remote does not have to be on GitHub: the trigger's `repo` filter decides what is
watched, and `remote` decides where the agent works. Clones use your normal Git
credentials.

## Agents { #agents }

```toml
[agents.defaults]
profile = "claude"    # used by automations that set no profile
timezone = "UTC"      # default timezone for cron automations

[agents.profiles.claude]
provider = "claude"
model = "sonnet"
```

Each profile sets a `provider`: `claude`, `codex`, `copilot`, `cursor`, `gemini`, `kilo`,
`opencode`, `pi`, or `qwen`. The other keys are options of that agent; see
[Coding agents](providers.md) for every option and the native flag it becomes.

## Assistant { #assistant }

`[assistant]` is optional and reserved for the interactive assistant of the
[terminal dashboard](tui.md#assistant).

| Key | Meaning |
| --- | --- |
| `agent` | A built-in provider name. `curupira validate` rejects unknown names. |
| `model` | A model id for that agent. Leave it out to use the agent's default. |

## Plugins { #plugins }

`[plugins.<alias>]` registers a package of triggers and how to start it. Automations then
use `trigger_type = "<alias>/<trigger>"`.

```toml
[plugins.plugins-py]
type = "uvx"
args = ["--from", "curupira-plugins", "curupira-plugins"]
tools = ["github-*"]

[plugins.acme-node]
type = "npx"
args = ["--yes", "@acme/curupira-ext@1.2.3"]
tools = ["*", "!internal-*"]
```

| Key | Required | Meaning |
| --- | --- | --- |
| `type` | yes | `uvx` or `npx`. That launcher must be on `PATH`. |
| `args` | yes | Arguments after the launcher, passed as a list and never through a shell. Pin versions. |
| `tools` | no | Glob patterns that select triggers. `!` excludes. Empty keeps every trigger. |

Connectors such as GitHub, and the ones in development, are listed under
[Plugins and connectors](plugins.md). To write your own, see
[Build extensions](extensions.md) and the [JavaScript SDK](extensions-javascript.md).

## Automations { #automations }

`[automations.<name>]` ties a trigger to a repository, an agent, and a prompt.

| Key | Required | Meaning |
| --- | --- | --- |
| `trigger_type` | yes | `<alias>/<trigger>` from a plugin, or `cron`. |
| `repository` | yes | A `[repositories.<alias>]` name. |
| `prompt` | yes | The message for the agent. See [Writing prompts](prompts.md). |
| `profile` | no | A profile name. Defaults to `[agents.defaults].profile`. |
| `checkout` | no | `worktree` (default) or `main`. See [Checkout and setup](#checkout). |

Every other key is passed to the trigger as its settings. The GitHub trigger takes `repo`,
`labels`, and other filters, documented on [Issues and pull requests](github.md) and
[Projects](github-projects.md). Cron takes `schedule` and the keys under
[Cron](automations.md#cron).

Automations are polled in file order. Prompt placeholders and conditions are covered in
[Writing prompts](prompts.md); [Prompt field reference](prompt-fields.md) lists what each
trigger provides.

## Checkout and setup { #checkout }

By default each task gets its own worktree and branch next to the clone
(`<clone>.worktrees/<automation>/…`, branch `curupira/<automation>/…`). The worktree is
removed when the task finishes, so tasks never share files.

`checkout = "main"` runs the agent in the shared clone instead. Curupira does not fetch,
pull, or switch branches in that mode; use it for read-only or scheduled jobs that should
see the clone as it is.

`setup_script` runs only after a fresh clone, in the clone, never in a worktree. A
non-zero exit stops the task. `run --dry-run` never clones or runs setup.

## Scheduling and state { #scheduling-and-state }

Each poll asks every automation's trigger for up to `batch_size` items. The fields of
each item are hashed into the task identity:

- A task that finished `ok` is stored in `state_db_path` and never runs again.
- The same item with a changed field (a new title, a new head commit) is a new identity,
  so it can run again.
- A failed task is not retried in the same process; the next `run` tries it again.

Filters such as `linked_pull_request = false` decide what the GitHub trigger returns; see
[Deduplication](github.md#deduplication) for how the GitHub triggers keep their output
stable. Cron automations produce one occurrence when the schedule is due and never run
twice at the same time.

Only one `run` or `tui` process dispatches at a time; it holds
`~/.curupira/dispatch.lock`. An incompatible state database is an error, never deleted
automatically.
