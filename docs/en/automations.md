# Automations reference

`curu` is the short alias for `curupira`; both run the same commands. This page is the
newcomer map for Curupira automations: which triggers exist, a minimal TOML example for
each, which prompt placeholders are available, and the first commands to run. Field-level
detail lives in the dedicated guides and in [Configuration](configuration.md); this page
summarizes and links.

An **automation** is one `[automations.<name>]` table. It watches a single source
(`trigger_type`), points at a `[repositories.<alias>]` Git repository, and carries a
`prompt` template for a coding-agent CLI. All automations share one discovery, scheduling,
and execution pipeline.

## Trigger overview

{{ triggers_table() }}

Installed [plugins](plugins.md) can add more trigger types. `curu plugins list` shows every
registered type and its prompt fields.

## Security: task text is untrusted

Titles and bodies from GitHub issues and pull requests, Azure DevOps pull requests, Trello
cards, and monday.com items are untrusted input. Curupira puts them into the coding-agent
prompt when the plugin returns those strings (`${issue_title}`, `${issue_body}`,
`${pull_request_title}`, `${pull_request_body}`, `${name}`, `${desc}`). A hostile author or board
editor can try to steer the agent. Restrict what reaches the agent with `labels`,
`author`, or `assignee` (GitHub), `list_ids` (Trello), or `group_ids` (monday.com). Review
what the agent profile is allowed to run in the repository. Only run automations on
repositories and boards where you trust everyone who can write text.

## First-use path

1. [Install Curupira](installation.md) and only the external CLIs your automations need
   (for example `gh`, `az`, `trello`, or a monday.com token) plus the coding-agent CLI in
   your profile:

   ```bash
   npm install -g @caipora/curupira
   # or: uv tool install curupira
   # forge triggers are optional PyPI extras, for example:
   # uv tool install 'curupira[github]'
   ```

2. Copy a minimal settings file (or start from `curupira.example.toml`), then validate
   without calling external CLIs or writing state:

   ```bash
   curupira --config path/to/settings.toml validate
   ```

3. Preview one matching task without cloning a repository or starting an agent:

   ```bash
   curupira --config path/to/settings.toml run --dry-run
   ```

4. Run all currently available tasks once (add `--size N` to limit), or keep polling with
   `--watch`:

   ```bash
   curupira --config path/to/settings.toml run
   curupira --config path/to/settings.toml run --size 1
   curupira --config path/to/settings.toml run --watch
   ```

`--dry-run` cannot be combined with `--watch` or `--size`. `--size` applies only when you
run tasks once (not with `--watch`). Operational details and exit codes are in
[Operations](operations.md).

Each example below repeats `[agents.defaults]` and `[agents.profiles.opencode]` so it
validates alone. In the cron example, `timezone = "UTC"` is the timezone used to evaluate
the schedule.

## GitHub issues

Finds issues using filters you set in TOML. Requires the
[GitHub CLI](https://cli.github.com/) (`gh auth login`). Full guide:
[GitHub task sources](github.md).

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "opencode"

[agents.profiles.opencode]
provider = "opencode"

[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
linked_pull_request = false
prompt = "Resolve issue ${issue_number}: ${issue_title}\n\n${issue_body}"
```

**Placeholders:** `${repository}` and `${automation}` from the host, plus the keys
this trigger returns, including `${repo}`, `${issue_number}`, `${issue_title}`,
`${issue_body}`, and `${issue_url}`.

**What the agent receives:** the rendered `prompt` string, with the agent working in the
Git repository named by `repository`. `${repo}` is a key the GitHub trigger returns;
`${repository}` is the forge identity derived from the Git remote.

## GitHub pull requests

Finds pull requests using filters you set in TOML (including optional merge checks after
listing). Requires `gh`. Full guide: [GitHub task sources](github.md).

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "opencode"

[agents.profiles.opencode]
provider = "opencode"

[automations.review-pull-requests]
trigger_type = "plugins-py/github-pull-requests"
repository = "api"
repo = "acme/api"
labels = ["review-needed"]
draft = false
prompt = """
Review pull request ${pull_request_number}: ${pull_request_title}

${pull_request_body}

Branch: ${pull_request_head_ref} -> ${pull_request_base_ref}
"""
```

**Placeholders:** `${repository}` and `${automation}` from the host, plus the keys
this trigger returns, including `${pull_request_number}`,
`${pull_request_title}`, `${pull_request_body}`, `${pull_request_url}`,
`${pull_request_is_draft}`, `${pull_request_head_ref}`, and
`${pull_request_base_ref}`.

**What the agent receives:** the rendered review prompt in the Git repository named by
`repository`. Booleans render as `true` / `false`. A field whose value is `None`
renders as `null`. A `${key}` the result does not contain is left unchanged.

## Azure DevOps pull requests

Lists Azure DevOps pull requests with `az repos pr list`. Requires the
[Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) with the Azure
DevOps extension (`az extension add --name azure-devops`), then `az login` (and
`az devops login` when required). Field reference:
[Configuration → Automations](configuration.md#automations).

```toml
[repositories.azure-api]
remote = "https://dev.azure.com/contoso/api-project/_git/api"

[agents.defaults]
profile = "opencode"

[agents.profiles.opencode]
provider = "opencode"

[automations.review-azure-pull-requests]
trigger_type = "plugins-py/azure-cli-pull-requests"
repository = "azure-api"
repo = "contoso/api-project/api"
prompt = """
Review pull request ${pull_request_number}: ${pull_request_title}

${pull_request_body}

URL: ${pull_request_url}
Branch: ${pull_request_head_ref} -> ${pull_request_base_ref}
"""
```

`repo` uses `organization/project/repository` (organization name, not a full URL).
Optional `status` (default `active`), `source_branch`, and `target_branch` filter the
Azure list. The agent still works in the Git repository from the `remote` (or `path`) on
the repository alias.

**Placeholders:** `${repository}` and `${automation}` from the host, plus the keys
this trigger returns: `${pull_request_number}`, `${pull_request_title}`,
`${pull_request_body}`, `${pull_request_url}`, `${pull_request_head_ref}`, and
`${pull_request_base_ref}`.

**What the agent receives:** the rendered prompt in the Git repository named by
`repository`. `${pull_request_title}` and `${pull_request_body}` are untrusted text, as
on GitHub.

## Trello cards

Finds open cards on a Trello board. Requires the `trello` CLI and `trello auth login`.
Full guide: [Trello task source](trello.md).

```toml
[repositories.product]
remote = "https://github.com/acme/product.git"

[agents.defaults]
profile = "opencode"

[agents.profiles.opencode]
provider = "opencode"

[automations.update-board-cards]
trigger_type = "plugins-py/trello-cli-cards"
repository = "product"
board_id = "66f6b55a1a2b3c4d5e6f7788"
list_ids = ["66f6b55a1a2b3c4d5e6f7790"]
prompt = "Handle Trello card ${id}: ${name}\n\n${desc}\n\n${url}"
```

**Placeholders:** `${repository}` and `${automation}` from the host, plus the keys
this trigger returns: `${id}`, `${name}`, `${url}`, `${desc}`, and `${list_name}`.

**What the agent receives:** the rendered card prompt in the Git repository named by
`repository`. `list_ids` is optional; when set, only cards in those lists are scheduled.

## monday.com items

Finds board items through monday.com's API (read-only). Export your personal API token as
`MONDAY_API_TOKEN` (see [Create an API token](monday.md#create-an-api-token)). For board
and group IDs, see [Find board and group IDs](monday.md#find-board-and-group-ids). Full
guide: [monday.com task source](monday.md).

```toml
[repositories.product]
remote = "https://github.com/acme/product.git"

[agents.defaults]
profile = "opencode"

[agents.profiles.opencode]
provider = "opencode"

[automations.board-items]
trigger_type = "plugins-py/monday-items"
repository = "product"
board_id = "1234567890"
group_ids = ["topics"]
# token_env = "MONDAY_API_TOKEN"
prompt = """
Handle monday.com item ${id}: ${name}

Group: ${group_title}
Board: ${board_id}
URL: ${url}
"""
```

**Placeholders:** `${repository}` and `${automation}` from the host, plus the keys
this trigger returns: `${id}`, `${name}`, `${url}`, `${board_id}`, and
`${group_title}`.

**What the agent receives:** the rendered item prompt in the Git repository named by
`repository`. `group_ids` is optional; when set, only items in those groups are scheduled.
The token owner must be able to open the board in the monday.com UI.

## Cron

Runs on a local schedule you set with a five-field `schedule`. No external board or issue
tracker CLI is required. Schedule options (timezone, start/end dates) are in
[Configuration](configuration.md#scheduling-and-state).

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "opencode"
timezone = "UTC"

[agents.profiles.opencode]
provider = "opencode"

[automations.weekly-maintenance]
trigger_type = "cron"
repository = "api"
schedule = "0 9 * * 1"
prompt = "Perform weekly maintenance for ${repository} (${automation})."
```

**Placeholders:** `${repository}` and `${automation}` only. Cron does not return
trigger pairs. Optional `timezone` overrides `[agents.defaults].timezone`; optional
`start_date` / `end_date` bound the inclusive window.

**What the agent receives:** the rendered maintenance prompt in the Git repository named
by `repository` when the schedule is due. Overdue runs are merged into one pending run,
and the same automation never runs twice at the same time.

## Common configuration errors

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `unknown trigger type: …` | Typo or plugin not installed | Check `trigger_type` against `curu plugins list` |
| Repository alias errors / missing repository | `repository` does not match a `[repositories.<alias>]` key | Align the alias and ensure `remote` is a full Git URL |
| Placeholder left unchanged in the prompt | `${name}` is not a host variable and the trigger did not return that key | Use a key the trigger returns; `curu plugins list` shows declared prompt fields |
| `Required executable not found: gh` / `az` / `trello` | CLI missing from `PATH` | Install and authenticate the CLI for that trigger |
| `monday.com API token is missing…` | `token_env` variable unset or empty | Export `MONDAY_API_TOKEN` (or your custom `token_env`) |
| `schedule must be a valid five-field cron expression` | Six-field cron or invalid expression | Use five fields (`minute hour day-of-month month day-of-week`) |
| `repo must use the owner/repository format` | GitHub `repo` not `owner/name` | Use `acme/api`, not a URL |
| `repo must use the organization/project/repository format` | Azure `repo` not three segments | Use `contoso/api-project/api` |
| No tasks scheduled | Filters match nothing | Widen or drop labels / `list_ids` / `group_ids` / branch filters; empty cycles are not an error |
| `validate` exits `2` | TOML shape or unknown configuration keys | Read the validation message; models reject unknown keys |

`curu validate` checks TOML shape and trigger configuration without calling external APIs.
It does not require prompt placeholders to match a fixed field list.
`curu run` and `curu run --watch` need the CLIs (or monday.com token) for your triggers
and the chosen agent CLI installed and authenticated.
