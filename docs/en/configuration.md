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

::: curupira.models.configuration.AzurePullRequestAutomationConfiguration

::: curupira.models.configuration.TrelloAutomationConfiguration

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

[automations.resolve-ready-issues]
trigger_type = "github-issues"
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
linked_pull_request = false
prompt = "Resolve issue ${issue_number}: ${issue_title}\n\n${issue_body}"
```

Save this as `~/.curupira/settings.toml`. The keys under `repositories`, `profiles`, and
`automations` are user-chosen identifiers; `repository` connects an automation to a
checkout alias, and `profile` connects it to a coding-agent profile.

Each profile's `provider` selects a registered coding agent: `claude`, `codex`, `copilot`,
`cursor`, `gemini`, `opencode`, `pi`, or `qwen`, plus any provider added by an installed
[agent plugin](plugins.md#agent-plugins). `curu plugins list` shows every available
provider and its executable.

## Assistant

`[assistant]` is optional. It records which registered coding-agent provider should run
the interactive configuration assistant and which model that CLI should use:

- `agent`: a provider name from the agent registry (the same identifiers used in profile
  `provider` values). Leave unset until you choose one.
- `model`: a concrete model id, or omit it to prefer the provider's native automatic
  selection when the adapter declares `auto_model` (Cursor documents `--model auto`).
  The literal `auto` is rejected for providers without that capability.

Existing TOML files without `[assistant]` keep the unset defaults.

## Repositories

`[repositories.<alias>]` owns Git checkout settings shared by one or more automations:

- `remote` (required): full Git URL used by `git clone` (HTTPS, SSH, or `user@host:path`).
- `path` (optional): existing checkout or alternate clone destination.
- `setup_script` (optional): repository-relative executable run only after a fresh clone.

Forge discovery is independent of the checkout URL. A common pattern is an Azure DevOps
`remote` with GitHub public issues: set `repositories.api.remote` to the Azure Git URL and
set the automation's GitHub `repo` to `owner/name`.

## Automations

`trigger_type` selects the source:

- `github-issues` discovers GitHub issues through GraphQL Search using typed filters
  (`labels`, `exclude_labels`, `assignee`, `linked_pull_request`, `sort`, …).
- `github-pull-requests` discovers GitHub pull requests the same way, with PR filters such
  as `draft`, `review`, `ci_status`, plus post-filters `mergeable` / `merge_state`.
- `azure-cli-pull-requests` lists Azure DevOps pull requests through `az repos pr list`.
- `trello-cli-cards` discovers Trello cards through Scale-Flow's `trello-cli` for a
  configured `board_id`, optionally restricted to `list_ids`.
- `cron` produces occurrences from a five-field `schedule` instead of querying a forge.
- Installed [plugins](plugins.md) add their own trigger types; `curu plugins list` shows
  every available type and its prompt placeholders.

Each automation requires `repository` (alias) and `prompt`. GitHub and Azure triggers also
require forge `repo` identity (`owner/name` or `organization/project/repository`). Cron
requires `schedule`. Trello automations require `board_id`. Optional `profile` selects a
CLI profile. Different repository aliases cannot share one workspace path. Automations keep
file order, and one-shot selection follows that order.

GitHub API authentication uses `gh auth token` from an already authenticated GitHub CLI.
Clone authentication uses native Git credentials for the configured `remote`.

Placeholders use `${name}` syntax and are validated when the configuration loads. Common
placeholders include `${repo}`, `${repository}`, `${automation_id}`, `${task_type}`,
`${task_number}`, `${task_title}`, `${task_body}`, and `${task_url}`. `${repo}` is the forge
identity when the trigger has one; `${repository}` is the checkout alias. Each trigger also
exposes the fields of its typed item model: issues provide `${issue_number}`,
`${issue_title}`, `${issue_body}`, and `${issue_url}`; pull requests provide
`${pull_request_number}`, `${pull_request_title}`, `${pull_request_body}`,
`${pull_request_url}`, `${pull_request_is_draft}`, `${pull_request_head_ref}`, and
`${pull_request_base_ref}`. For cron tasks, `${task_number}` is the occurrence timestamp.

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

`max_active_tasks` bounds concurrent agents. Checkouts using the same path run sequentially.
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
