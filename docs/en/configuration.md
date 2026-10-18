# Configuration

## Generated model reference

The model reference below is generated from the public Pydantic models. Field types,
defaults, and constraints come directly from the source models; update those models rather
than maintaining a parallel field table here.

### Runtime settings

::: curupira.models.configuration.ExecutionSettings
    options:
      members:
        - max_active_tasks
        - max_pending_tasks
        - workspace_dir
        - state_db_path
        - otlp_endpoint
        - log_level
        - task_timeout_minutes
        - max_output_bytes
        - polling

::: curupira.models.configuration.PollingSettings
    options:
      show_root_heading: true

### Repositories, agents, and automations

::: curupira.models.configuration.RepositoryConfiguration

::: curupira.models.configuration.AgentDefaults

::: curupira.models.configuration.AgentsSettings

::: curupira.models.configuration.AssistantSettings

::: curupira.models.configuration.IssueAutomationConfiguration

::: curupira.models.configuration.PullRequestAutomationConfiguration

::: curupira.models.configuration.CronAutomationConfiguration

### CLI profiles

::: curupira.models.profiles.OpenCodeCliProfile

::: curupira.models.profiles.CodexCliProfile

::: curupira.models.profiles.ClaudeCodeCliProfile

::: curupira.models.profiles.CursorCliProfile

The GitHub Copilot CLI profile is documented on its [provider page](providers/copilot.md#configuration-reference).

One TOML file separates runtime limits, Git repositories, coding-agent profiles, and
automations. An automation watches issues, pull requests, cards, or a cron schedule, and
points at a repository alias for checkout.

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
cron_poll_interval_seconds = 1

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

Save this as `~/.curupira/settings.toml`. The keys under `repositories`, `profiles`,
`plugins`, and `automations` are user-chosen identifiers; `repository` connects an
automation to a checkout alias, `profile` connects it to a coding-agent profile, and
`[plugins.<alias>]` registers a trigger launcher so automations can use
`<alias>/<local-trigger>` (for example `plugins-py/github-issues`).

Each profile's `provider` selects a **built-in** coding agent: `claude`, `codex`, `copilot`,
`cursor`, `gemini`, `kilo`, `opencode`, `pi`, or `qwen`. Coding agents are part of the Rust
CLI (not process extensions). `curu plugins list` shows those providers as
`agent:<name>` with origin `built-in`, alongside trigger extensions.

## Assistant

`[assistant]` is optional. It records which built-in coding-agent provider should run
the interactive configuration assistant and which model that CLI should use:

- `agent`: a built-in provider name (the same identifiers used in profile `provider`
  values). Leave unset until you choose one.
- `model`: a concrete model id, or omit it to prefer the provider's native automatic
  selection when the adapter documents one (`auto` for Cursor, Gemini CLI, and GitHub
  Copilot CLI). The literal `auto` is rejected for providers without that capability.

Existing TOML files without `[assistant]` keep the unset defaults.

`curu tui` currently runs continuous dispatch with status lines; a full embedded assistant
panel is follow-up work. Interactive launch recipes for each built-in provider are still
implemented in the Rust core for that future surface.

## Plugins

`[plugins.<alias>]` registers a trigger under a settings alias and declares how to launch
it. `uvx` and `npx` are independent launchers; `args` are passed to that tool as argv
(never a shell string). The host discovers trigger types by spawning the process and
calling `describe`, then applies an optional `tools` filter:

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

- `type` (required): `uvx` or `npx`.
- `args` (required, non-empty): arguments after the launcher binary. Official Python
  plugins expose a `curupira-plugins` console script, so end users run
  `uvx --from curupira-plugins curupira-plugins` (no `python -m`).
- `tools` (optional): glob list selecting which local trigger names to expose. Empty or
  omitted keeps every trigger from `describe`. Positive patterns (`github-*`, `*`) are
  includes; patterns starting with `!` (`!github-project-*`) are excludes. A name must match an
  include when any includes are set, and must not match any exclude.

Automations then set `trigger_type = "<alias>/<local-trigger>"`. Local trigger names are
kebab-case names declared by the extension (for example `github-issues`). The official
`curupira-plugins` distribution is usually registered as `plugins-py` with `type = "uvx"`.

## Repositories

`[repositories.<alias>]` owns Git checkout settings shared by one or more automations:

- `remote` (required): full Git URL used by `git clone` (HTTPS, SSH, or `user@host:path`).
- `path` (optional): existing checkout or alternate clone destination.
- `setup_script` (optional): repository-relative executable run only after a fresh clone.

Forge discovery is independent of the checkout URL. A common pattern is a `remote`
on a different host than GitHub with GitHub public issues: set `repositories.api.remote` to
that Git URL and set the automation's GitHub `repo` to `owner/name`.

## Automations

`trigger_type` selects the source:

- `plugins-py/github-issues` discovers GitHub issues through GraphQL Search using typed filters
  (`labels`, `exclude_labels`, `assignee`, `linked_pull_request`, `sort`, …). Set
  `linked_pull_request = false` so discovery compiles `-linked:pr` and skips issues that
  already have a linked pull request. That filter is configuration-time discovery only;
  see [Scheduling and state](#scheduling-and-state) for scheduler revalidation of recovered
  sessions.
- `plugins-py/github-pull-requests` discovers GitHub pull requests the same way, with PR filters such
  as `draft`, `review`, `ci_status`, plus post-filters `mergeable` / `merge_state`.
- `cron` produces occurrences from a five-field `schedule` instead of querying a forge.
- Installed [trigger extensions](extensions.md) add their own trigger types;
  `curu plugins list` shows every available type.

Each automation requires `repository` (alias) and `prompt`. GitHub triggers also
require forge `repo` identity (`owner/name`). Cron requires `schedule`. Optional `profile`
selects a CLI profile. Different repository aliases cannot share one workspace path. Automations keep
file order, and one-shot selection follows that order.

GitHub API authentication uses `gh auth token` from an already authenticated GitHub CLI.
Clone authentication uses native Git credentials for the configured `remote`.

Placeholders use `${name}` syntax (Jinja conditionals and loops are also available; see
[Writing prompts](prompts.md)) and are validated when the configuration loads. Common
placeholders include `${repo}`, `${repository}`, `${automation_id}`, `${task_type}`,
`${task_number}`, `${task_title}`, `${task_body}`, and `${task_url}`. `${repo}` is the forge
identity when the trigger has one; `${repository}` is the checkout alias. Each trigger also
exposes the fields of its typed item model: issues provide `${issue_number}`,
`${issue_title}`, `${issue_body}`, and `${issue_url}`; pull requests provide
`${pull_request_number}`, `${pull_request_title}`, `${pull_request_body}`,
`${pull_request_url}`, `${pull_request_is_draft}`, `${pull_request_head_ref}`,
`${pull_request_base_ref}`, and optional refreshed metadata such as
`${pull_request_head_sha}` and `${pull_request_mergeable}`. For cron tasks,
`${task_number}` is the occurrence timestamp.

## Checkout and setup

Each task uses its own worktree by default, created from the fetched remote default branch.
Set `checkout = "main"` to use the shared checkout as-is; Curupira does not fetch, pull, or
switch branches in that mode. The repository alias's `path` selects the base checkout.
Clones use `git clone <remote>`.

`setup_script` lives on the repository alias. It runs directly only after a base checkout
is freshly cloned, not for an existing checkout or in a task worktree. A nonzero exit
prevents the agent from starting and removes the newly cloned checkout. Validation checks
path syntax but does not require the script to exist. `run --dry-run` does not fetch, clone,
create worktrees, or run setup.

## Scheduling and state

Polls fetch up to `batch_size` items (default 100, maximum 1000). Empty poll cycles back off
from `poll_interval_seconds` (default 30 seconds) up to five minutes; discovery resets the
wait. Automations deduplicate independently.

Discovery filters such as `linked_pull_request = false` (`-linked:pr`) only affect what
GitHub Search returns for new work. They do not protect recovered sessions that were saved
before an issue gained a linked PR. Scheduler enforcement is separate: before a new task or
saved session is admitted, Curupira fetches the current issue or pull-request state once,
drops closed or merged items, rejects an issue that already has an open closing or
Development-linked PR (via GraphQL `closedByPullRequestsReferences`, including body forms
such as `Fixes: #N`), retires its stale issue session, and restarts a PR session when the
head SHA, draft flag, title, or body no longer matches the saved snapshot. Pull-request
sessions recovered from a state database written before head SHA was persisted restart once
when the refreshed snapshot supplies a head. If GitHub reports more closing-PR references
than one GraphQL page, admission fails closed for that candidate (no agent). A transient
revalidation error defers that candidate, keeps any saved session, and does not stop the
scheduler.

One-shot and initial polls call every automation feed together. A `DispatchError` from one
feed is logged and that feed contributes no tasks; other feeds still return candidates.
`run` (one-shot) then tries candidates in order and moves to the next when revalidation
discards one. Continuous `run --watch` / `tui` streams already logged per-feed discovery
errors the same way.

After a successful agent run (the coding-agent CLI actually executed), Curupira stores the
completed source fingerprint plus an explicit next action in `state_db_path`. An unchanged
completed snapshot is skipped across dispatch cycles. Fingerprints use head SHA, draft flag,
title, and body — not mergeability, merge-state status, or check conclusions — so check or
conflict transitions alone do not re-admit work. A changed head, draft flag, title, or body
can be admitted again. If completion verification itself fails, Curupira clears any completed
record for that item so the next cycle retries verification instead of skipping forever.
Snapshots skipped as obsolete before the agent starts are not recorded as completed.

Finite `run --size N` drains admit at most `N` tasks after revalidation. Recovered sessions
count toward `N`; candidates discarded during revalidation do not.

`max_active_tasks` bounds concurrent agents (worker slots). When a task finishes, its slot is
refilled by the next poll right away. Tasks that share a base checkout serialize their clone
and worktree setup, but their agents run in parallel. A task that fails is not retried within
the same `run` invocation; it is picked up again by the next one.
Cron automations coalesce overdue ticks into one pending occurrence and never run themselves
concurrently. `schedule` uses five cron fields; `timezone` is an IANA zone (default UTC),
and optional `start_date`/`end_date` define an inclusive window. Without `start_date`, the
window starts when the automation is first recorded. `task_timeout_minutes` (default 20) is
the deadline for one coding-agent run and its optional setup script.

State is stored in `state_db_path` (default `~/.curupira/state.sqlite3`), the dispatch lock
in `~/.curupira/dispatch.lock`, and logs in `~/.curupira/logs`. An incompatible database
causes an error rather than automatic deletion. Only one `run` or `tui` process may dispatch
at a time.

## Telemetry

Set `settings.otlp_endpoint` to an OTLP/HTTP trace endpoint (for example,
`http://localhost:4318/v1/traces`) to export one span per dispatched task. If omitted, no
telemetry is exported.
