# Automations reference

This page is the newcomer map for Curupira automations: which triggers exist, a minimal
TOML example for each, which prompt placeholders are available, and the first commands to
run. Field-level detail lives in the dedicated guides and in
[Configuration](configuration.md); this page summarizes and links.

An **automation** is one `[automations.<name>]` table. It watches a single source
(`trigger_type`), points at a `[repositories.<alias>]` checkout, and carries a `prompt`
template for a coding-agent CLI. All automations share one discovery, scheduling, and
execution pipeline.

## Trigger overview

{{ triggers_table() }}

Installed [plugins](plugins.md) can add more trigger types. `curu plugins list` shows every
registered type and its prompt fields.

## Security: task text is untrusted

Titles and bodies from issues, pull requests, Trello cards, and monday.com items are
**untrusted input**. Curupira interpolates them into the coding-agent prompt
(`${issue_title}`, `${issue_body}`, `${pull_request_title}`, `${pull_request_body}`,
`${card_title}`, `${card_body}`, `${item_name}`, `${item_columns}`, and the shared
`${task_title}` / `${task_body}` fields). A hostile author or board editor can try to
steer the agent (prompt injection). Restrict what reaches the agent with
`labels` / `author` / `assignee` (GitHub), `list_ids` (Trello), `group_ids` (monday.com),
or the equivalent filters for your trigger, and review what the agent profile is allowed
to run in the checkout.

## First-use path

1. [Install Curupira](installation.md) and only the forge / coding-agent CLIs your
   automations need:

   ```bash
   uv tool install curupira
   ```

2. Copy a minimal settings file (or start from `curupira.example.toml`), then validate
   without calling external CLIs or writing state:

   ```bash
   curupira --config path/to/settings.toml validate
   ```

3. Preview one matching task without reserving cron occurrences, cloning, or starting an
   agent:

   ```bash
   curupira --config path/to/settings.toml run --dry-run
   ```

4. Drain currently available tasks once, optionally capped with `--size`, or poll
   continuously:

   ```bash
   curupira --config path/to/settings.toml run
   curupira --config path/to/settings.toml run --size 1
   curupira --config path/to/settings.toml run --watch
   ```

`--dry-run` cannot be combined with `--watch` or `--size`. `--size` applies to a finite
`run` drain only. The short alias `curu` accepts the same commands. Operational details
and exit codes are in [Operations](operations.md).

## GitHub issues

Discovers issues in one `owner/repository` through typed filters compiled to GraphQL
Search. Requires the [GitHub CLI](https://cli.github.com/) (`gh auth login`). Full guide:
[GitHub task sources](github.md).

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "opencode"

[agents.profiles.opencode]
provider = "opencode"

[automations.resolve-ready-issues]
trigger_type = "github-issues"
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
linked_pull_request = false
prompt = "Resolve issue ${issue_number}: ${issue_title}\n\n${issue_body}"
```

**Placeholders:** common fields
(`${repo}`, `${repository}`, `${automation_id}`, `${task_type}`, `${task_number}`,
`${task_title}`, `${task_body}`, `${task_url}`) plus
`${issue_number}`, `${issue_title}`, `${issue_body}`, `${issue_url}`.

**What the agent receives:** the rendered `prompt` string in a Git checkout for
`repository` (worktree by default). `${repo}` is the forge identity; `${repository}` is
the checkout alias.

## GitHub pull requests

Discovers pull requests the same way as issues, with PR-specific Search filters and
optional merge post-filters. Requires `gh`. Full guide: [GitHub task sources](github.md).

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "opencode"

[agents.profiles.opencode]
provider = "opencode"

[automations.review-pull-requests]
trigger_type = "github-pull-requests"
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

**Placeholders:** common fields plus
`${pull_request_number}`, `${pull_request_title}`, `${pull_request_body}`,
`${pull_request_url}`, `${pull_request_is_draft}`, `${pull_request_head_ref}`,
`${pull_request_base_ref}`.

**What the agent receives:** the rendered review prompt in the automation's checkout.
Booleans render as `true` / `false`; missing optional values render as empty strings.

## Azure DevOps pull requests

Discovers pull requests through `az repos pr list`. Requires the
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
trigger_type = "azure-cli-pull-requests"
repository = "azure-api"
repo = "contoso/api-project/api"
prompt = """
Review pull request ${pull_request_number}: ${pull_request_title}

${pull_request_body}

Repository: ${repo}
URL: ${pull_request_url}
Branch: ${pull_request_head_ref} -> ${pull_request_base_ref}
"""
```

`repo` uses `organization/project/repository` (organization name, not a full URL).
Optional `status` (default `active`), `source_branch`, and `target_branch` filter the
Azure list. Cloning still uses the repository alias `remote` (native Git) unless `path`
points at an existing checkout.

**Placeholders:** common fields plus the same pull-request fields as GitHub
(`${pull_request_number}`, `${pull_request_title}`, `${pull_request_body}`,
`${pull_request_url}`, `${pull_request_is_draft}`, `${pull_request_head_ref}`,
`${pull_request_base_ref}`).

**What the agent receives:** the rendered prompt in the Azure (or other) checkout named
by `repository`.

## Trello cards

Discovers open cards on one board through Scale-Flow's `trello-cli`. Requires the CLI and
`trello auth login`. Full guide: [Trello task source](trello.md).

```toml
[repositories.product]
remote = "https://github.com/acme/product.git"

[agents.defaults]
profile = "opencode"

[agents.profiles.opencode]
provider = "opencode"

[automations.update-board-cards]
trigger_type = "trello-cli-cards"
repository = "product"
board_id = "66f6b55a1a2b3c4d5e6f7788"
list_ids = ["66f6b55a1a2b3c4d5e6f7790"]
prompt = "Handle Trello card ${card_id}: ${card_title}\n\n${card_body}\n\n${card_url}"
```

**Placeholders:** common fields plus
`${card_id}`, `${card_title}`, `${card_body}`, `${card_url}`, `${card_list_id}`.

**What the agent receives:** the rendered card prompt in the `product` checkout.
`list_ids` is optional; when set, only cards in those lists are scheduled.

## monday.com items

Discovers board items through the monday.com GraphQL API over `httpx` (read-only). Set a
personal API token in `MONDAY_API_TOKEN` (or the environment variable named by
`token_env`). Full guide: [monday.com task source](monday.md).

```toml
[repositories.product]
remote = "https://github.com/acme/product.git"

[agents.defaults]
profile = "opencode"

[agents.profiles.opencode]
provider = "opencode"

[automations.board-items]
trigger_type = "monday-items"
repository = "product"
board_id = "1234567890"
group_ids = ["topics"]
# token_env = "MONDAY_API_TOKEN"
prompt = """
Handle monday.com item ${item_id}: ${item_name}

Group: ${item_group_title} (${item_group_id})
Board: ${board_id}
State: ${item_state}
URL: ${item_url}

${item_columns}
"""
```

**Placeholders:** common fields plus
`${item_id}`, `${item_name}`, `${item_url}`, `${item_group_id}`, `${item_group_title}`,
`${board_id}`, `${item_state}`, `${item_columns}`.

**What the agent receives:** the rendered item prompt in the checkout. `group_ids` is
optional; when set, only items in those groups are scheduled. The token owner must be
able to open the board in the monday.com UI.

## Cron

Produces local occurrences from a five-field `schedule` instead of querying a forge. No
forge CLI is required. Semantics (coalescing, timezone, date window) are in
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
prompt = "Perform weekly maintenance for ${repository} (occurrence ${task_number})."
```

**Placeholders:** common fields only. For cron tasks, `${task_number}` is the occurrence
timestamp. Optional `timezone` overrides `[agents.defaults].timezone`; optional
`start_date` / `end_date` bound the inclusive window.

**What the agent receives:** the rendered maintenance prompt in the checkout when the
schedule is due. Overdue ticks coalesce into one pending occurrence; the same automation
never runs concurrently with itself.

## Common configuration errors

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `unknown trigger type: …` | Typo or plugin not installed | Check `trigger_type` against `curu plugins list` |
| Repository alias errors / missing checkout | `repository` does not match a `[repositories.<alias>]` key | Align the alias and ensure `remote` is a full Git URL |
| Unknown prompt placeholder | `${name}` not in the common set or the trigger's item fields | Fix the placeholder; `curu plugins list` shows trigger fields |
| `Required executable not found: gh` / `az` / `trello` | Forge CLI missing from `PATH` | Install and authenticate the CLI for that trigger |
| `monday.com API token is missing…` | `token_env` variable unset or empty | Export `MONDAY_API_TOKEN` (or your custom `token_env`) |
| `schedule must be a valid five-field cron expression` | Six-field cron or invalid expression | Use five fields (`minute hour day-of-month month day-of-week`) |
| `repo must use the owner/repository format` | GitHub `repo` not `owner/name` | Use `acme/api`, not a URL |
| `repo must use the organization/project/repository format` | Azure `repo` not three segments | Use `contoso/api-project/api` |
| No tasks scheduled | Filters match nothing | Widen or drop labels / `list_ids` / `group_ids` / branch filters; empty cycles are not an error |
| `validate` exits `2` | TOML shape, unknown keys, or placeholder errors | Read the validation message; models reject unknown keys |

`curupira validate` checks TOML shape and prompt placeholders without calling forge APIs.
`curupira run` and `curupira run --watch` need the forge CLIs (or monday.com token) and
the chosen agent CLI installed and authenticated.
