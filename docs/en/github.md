# GitHub issues and pull requests

Curupira discovers GitHub issues and pull requests with typed TOML filters, compiles them
into [GitHub Search](https://docs.github.com/en/search-github/searching-on-github/searching-issues-and-pull-requests)
queries, and runs those queries through the GraphQL API. Authentication is a bearer token
from `gh auth token`. Curupira does not create, edit, close, or comment on issues or pull
requests.

Each match becomes a **task**: a typed item (issue or pull request fields), an identity used
for deduplication, a rendered prompt for a coding-agent CLI, and a local Git checkout or
worktree where that agent runs.

| Trigger type | What it discovers |
| --- | --- |
| `plugins-py/github-issues` | Issues in one `owner/repository` |
| `plugins-py/github-pull-requests` | Pull requests in one `owner/repository` |
| `plugins-py/github-project-items` | Issues and pull requests in a column of a GitHub Project board. See [GitHub Projects](github-projects.md) |

## Prerequisites

1. Install the [GitHub CLI](https://cli.github.com/) (`gh`).
2. Authenticate once:

   ```sh
   gh auth login
   ```

3. Confirm `gh` has a token (Curupira reads it with the same command):

   ```sh
   gh auth token
   ```

Curupira does not store GitHub credentials. It runs `gh auth token` (cached for five minutes)
and sends that bearer token to `https://api.github.com/graphql`. Clone and worktree
operations use native `git` and your normal Git credentials for the repository `remote`, not
`gh repo clone`.

### Token scopes

Use a token with the `repo` scope for private repositories, or `public_repo` when you only
need public repositories. Check `gh auth status` for the scopes on your current login.
Curupira itself only reads Search results; the coding agent it launches may do more,
depending on its profile. See
[GitHub's GraphQL authentication guide](https://docs.github.com/en/graphql/guides/forming-calls-with-graphql#authenticating-with-graphql)
for how requested data maps to scopes.

## Minimal issue automation { #minimal-issue-automation }

In an automation, `repo` is the GitHub `owner/name` that Curupira searches. `repository` is
the alias of a `[repositories.<alias>]` checkout where the agent runs. They can differ.

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "opencode-default"
timezone = "UTC"

[agents.profiles.opencode-default]
provider = "opencode"

[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
linked_pull_request = false
prompt = "Resolve issue ${issue_number}: ${issue_title}\n\n${issue_body}"
```

Validate without contacting GitHub:

```sh
curupira --config path/to/settings.toml validate
```

## Minimal pull-request automation

`repo` and `repository` mean the same as in [Minimal issue automation](#minimal-issue-automation).

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "opencode-default"
timezone = "UTC"

[agents.profiles.opencode-default]
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

## Dependabot pull-request automation

Filter to one author with `author = "app/dependabot"` and require `mergeable = true` so
conflicting pull requests are left alone. The prompt below only uses placeholders listed above,
and `${repo}` carries the `owner/name` used for every `gh` command. The agent profile needs
`auto_approve = true` so unattended `gh` writes (push, `gh pr merge`) do not stop for approval.

```toml
[automations.merge-dependabot-pull-requests]
trigger_type = "plugins-py/github-pull-requests"
repository = "curupira"
repo = "caipora-labs/curupira"
author = "app/dependabot"
state = "open"
draft = false
mergeable = true
sort = "created-asc"
prompt = """
Analyze Dependabot pull request #${pull_request_number} (${pull_request_title}) in ${repo}.
Fix what the update breaks, wait for the checks, then squash-merge it with
`gh pr merge ${pull_request_number} --repo ${repo} --squash`.
"""
```

Run it until the open Dependabot pull requests are handled:

```sh
curupira --config path/to/settings.toml run --watch --size 12
```

## First run

1. Install and authenticate the coding-agent CLI named by your profile (`opencode` in the
   snippets above). Provider-native options and setup notes are on the
   [Providers and agents](providers.md) pages.
2. Preview one matching task without cloning or starting an agent:

   ```sh
   curupira --config path/to/settings.toml run --dry-run
   ```

3. Drain currently available tasks once, or poll continuously:

   ```sh
   curupira --config path/to/settings.toml run
   curupira --config path/to/settings.toml run --watch
   ```

`--dry-run` cannot be combined with `--watch` or `--size`. `validate` checks TOML shape
and prompt placeholders without calling GitHub; `run` and `run --watch` need `gh` and the
chosen agent CLI installed and authenticated.

## Configuration fields

Models reject unknown keys.

### Shared automation fields

| Field | Default | Notes |
| --- | --- | --- |
| `trigger_type` | see notes | Set explicitly to `"plugins-py/github-issues"` or `"plugins-py/github-pull-requests"`. If omitted when parsing TOML, Curupira chooses `"plugins-py/github-issues"` only when the table has no `schedule`; a `schedule` key defaults to `"cron"` instead |
| `repository` | *(required)* | Alias of a `[repositories.<alias>]` entry |
| `checkout` | `"worktree"` | `"worktree"` or `"main"` (shared checkout, not a branch name) |
| `prompt` | *(required)* | Non-empty `string.Template` with `${placeholders}` |
| `profile` | `None` | Named CLI profile; otherwise `agents.defaults.profile`, which defaults to `"opencode"`. See [Providers and agents](providers.md) for profile options |

### Shared GitHub filters

Compiled into the Search query.

| Field | Default | Search qualifier / behavior |
| --- | --- | --- |
| `repo` | *(required)* | `repo:owner/name` (`owner/repository` format) |
| `state` | `"open"` | `"open"` → `is:open`; `"closed"` → `is:closed`; `"all"` → neither. For pull requests, `is:closed` includes merged PRs |
| `labels` | `()` | One label or a list. Each value → `label:…` (AND: every label must be present) |
| `exclude_labels` | `()` | One label or a list. Each value → `-label:…` |
| `assignee` | `None` | Login, `@me`, `none` → `no:assignee`, or `any` → `assignee:*` |
| `author` | `None` | `author:…` |
| `milestone` | `None` | `milestone:…` |
| `project` | `None` | `project:<value>`, for example `acme/5` |
| `sort` | `"created-asc"` | Appended as `sort:…`. Allowed: `created-asc`, `created-desc`, `updated-asc`, `updated-desc`, `comments-asc`, `comments-desc` |

The `project` qualifier only restricts which project an item belongs to. To pick items by
board column, use [`github-project-items`](github-projects.md). Values with whitespace or `"`, `:`, `,` are quoted in the
compiled query.

### Issue-only fields

| Field | Default | Behavior |
| --- | --- | --- |
| `linked_pull_request` | `None` | `true` → `linked:pr`; `false` → `-linked:pr`; omit for no filter |

### Pull-request-only fields

| Field | Default | Behavior |
| --- | --- | --- |
| `draft` | `None` | `true` → `draft:true`; `false` → `draft:false` |
| `base` | `None` | `base:…` |
| `head` | `None` | `head:…` |
| `review` | `None` | `review:…` — `none`, `required`, `approved`, or `changes_requested` |
| `ci_status` | `None` | `status:…` — `success`, `failure`, or `pending` |
| `linked_issue` | `None` | `true` → `linked:issue`; `false` → `-linked:issue` |
| `mergeable` | `None` | GraphQL post-filter: `true` keeps `MERGEABLE`; `false` keeps `CONFLICTING` |
| `merge_state` | `()` | GraphQL post-filter: keep only listed `mergeStateStatus` values (`BEHIND`, `BLOCKED`, `CLEAN`, `DIRTY`, `DRAFT`, `HAS_HOOKS`, `UNKNOWN`, `UNSTABLE`) |

`mergeable` and `merge_state` are applied after Search returns results; they are not Search
qualifiers.

### Related polling settings

Under `[settings.polling]`:

| Field | Default |
| --- | --- |
| `poll_interval_seconds` | `30.0` |
| `batch_size` | `100` (maximum 1000) |
| `cron_poll_interval_seconds` | `1.0` |

## How issues and pull requests are selected

Every poll builds a query that always starts with `repo:<repo>` and either `is:issue` or
`is:pr`, then appends the filters above and `sort:<sort>`. Example for the minimal issue
automation:

```text
repo:acme/api is:issue is:open label:agent-ready -linked:pr sort:created-asc
```

Discovery uses GraphQL Search (`ISSUE` search type covers both issues and pull requests).
There is no free-form `query` field: filters are typed TOML only.

### Deduplication { #deduplication }

A task is identified by `[automation_id, repo, task_type, id]`. Curupira keeps two records:

- **Completed tasks are remembered across restarts.** When the agent finishes successfully,
  the task is stored in the state database (`state_db_path`) and is never run again for that
  automation, even if the item still matches your filters.
- **Failed tasks are retried.** A task whose agent run failed is not stored as completed. It is
  skipped for the rest of the current process and tried again after a restart.

Deduplication is per automation, so two automations may process the same issue or pull request
with different prompts. `run --dry-run` previews without recording anything.

!!! tip "Running an item again"
    To run a completed item again, use a different automation name (a new automation has its own
    history) or remove the row from the state database. Changing the filters alone does not
    make a completed item eligible again.

When a full cycle finds nothing (or discovery fails), the feed waits
`poll_interval_seconds`, then doubles the wait on consecutive empty cycles up to five
minutes (`300` seconds). Any successful discovery resets the interval.

## What the agent prompt receives

The prompt can use `${field}` or Jinja syntax, see [Writing prompts](prompts.md). Every field
of issues and pull requests (title, body, labels, assignees, comments, review state, CI status,
and more) is listed in the [Prompt field reference](prompt-fields.md).

## Security: issue and pull-request text is untrusted { #security }

Titles, bodies, and comments (`${issue_title}`, `${issue_body}`, `${issue_comments}`,
`${pull_request_title}`, `${pull_request_body}`, `${pull_request_comments}`, `${item_body}`,
`${item_comments}`) come from anyone who can open an issue or pull request and are
placed in the coding agent's prompt, so a hostile author can try to steer the agent
(prompt injection). The agent can run destructive actions in the checkout it works in,
so the risk depends on what you allow in the agent profile. Restrict what reaches the
agent with `labels` (applied only by people you trust), `author` or `assignee`, and
review what your agent profile is allowed to run.

## Checkout and worktrees

GitHub triggers use the default native Git version control.

1. Curupira clones `repositories.<alias>.remote` into `workspace_dir/<alias>` (or the
   alias `path`) on first use.
2. With `checkout = "worktree"` (default), it fetches `origin`, resolves the remote default
   branch, and adds a worktree at
   `<checkout>.worktrees/<automation_id>/<task_type>-<sha256(task_id)>` on branch
   `curupira/<automation_id>/<task_type>-<sha256(task_id)>`. The branch is not pushed.
3. With `checkout = "main"`, the agent runs on the shared checkout as-is: no fetch, pull, or
   branch switch.
4. After the agent finishes, Curupira removes the worktree and deletes the local branch
   (cleanup failures are logged, not fatal).

Optional `setup_script` on the repository alias runs only after a fresh clone of the base
checkout, not inside the worktree.

### Agent isolation

The agent process runs with its working directory and `PWD` set to the worktree, and without
the `GIT_DIR`, `GIT_WORK_TREE`, and `GIT_INDEX_FILE` variables that would point Git at another
repository. Your own checkout is never switched by an automation. For OpenCode, Curupira also
passes `--dir <worktree>` and gives each task its own `OPENCODE_DB` at `<worktree>.opencode.db`,
so OpenCode sessions and project entries stay with that task. Other agent-wide state, such as
the global OpenCode configuration and credentials, is still shared.

## Common errors

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `Required executable not found: gh` | GitHub CLI missing from `PATH` | Install `gh` and retry |
| `gh exited with status …` / empty token | Not logged in, or token unavailable | Run `gh auth login`, then `gh auth token` |
| GraphQL / HTTP 401 or scope errors | Token lacks access to the repository or Search | Re-run `gh auth login` so the token includes `repo`, or use a classic PAT with the scopes required by [GitHub's GraphQL guide](https://docs.github.com/en/graphql/guides/forming-calls-with-graphql#authenticating-with-graphql) |
| No tasks scheduled | Filters match nothing | Widen labels/state, drop `linked_*` / `draft` filters, or confirm `repo` is correct; empty cycles are not an error |
| `GitHub GraphQL temporarily failed with status 429` (or similar) | Rate limit or transient API failure | Curupira retries transient errors a few times; back off or reduce poll frequency / `batch_size` |
| Discovery warnings in `run --watch` | GraphQL or CLI failure treated as an empty cycle | Check logs for `Discovery failed for …`; fix auth or network, then wait for the next poll |

`curupira validate` checks TOML shape and prompt placeholders without calling GitHub.
`curupira run` and `curupira run --watch` need `gh` installed and authenticated.
