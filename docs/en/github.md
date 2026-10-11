# GitHub task sources

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
| `github-issues` | Issues in one `owner/repository` |
| `github-pull-requests` | Pull requests in one `owner/repository` |

Implementation lives under `src/curupira/providers/github/` (`issues.py`, `pull_requests.py`),
with compatibility re-exports at `curupira.tasks.github_issues` and
`curupira.tasks.github_pull_requests`.

## Prerequisites

1. Install the [GitHub CLI](https://cli.github.com/) (`gh`).
2. Authenticate once:

   ```sh
   gh auth login
   ```

3. Confirm Curupira can read a token:

   ```sh
   gh auth token
   ```

Curupira does not store GitHub credentials. It runs `gh auth token` (cached for five minutes)
and sends that bearer token to `https://api.github.com/graphql`. Clone and worktree
operations use native `git` and your normal Git credentials for the repository `remote`, not
`gh repo clone`.

### Token scopes

The [GitHub CLI `gh auth login` manual](https://cli.github.com/manual/gh_auth_login) states
that tokens passed with `--with-token` need at least `repo`, `read:org`, and `gist`. A
normal browser `gh auth login` already requests that minimum set (including `repo`), which
covers GraphQL Search of issues and pull requests for repositories the account can access.

[GitHub's GraphQL authentication guide](https://docs.github.com/en/graphql/guides/forming-calls-with-graphql#authenticating-with-graphql)
notes that the data you request dictates the scopes or permissions needed, and that a
classic PAT needs `public_repo` to access public repositories when broader `repo` is not
granted. Curupira only reads Search results; it never mutates forge objects.

## Minimal issue automation

`repository` is a `[repositories.<alias>]` checkout key. `repo` is the GitHub
`owner/name` identity used for Search (independent of the clone URL).

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"

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

Validate without contacting GitHub:

```sh
curupira --config path/to/settings.toml validate
```

## Minimal pull-request automation

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "opencode-default"
timezone = "UTC"

[agents.profiles.opencode-default]
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

Defaults come from `IssueAutomationConfiguration` /
`PullRequestAutomationConfiguration` in `src/curupira/models/configuration.py` and the
shared bases they extend. Models are frozen and reject unknown keys (`extra="forbid"`).

### Shared automation fields

| Field | Default | Notes |
| --- | --- | --- |
| `trigger_type` | see notes | Set explicitly to `"github-issues"` or `"github-pull-requests"`. If omitted when parsing TOML, Curupira chooses `"github-issues"` only when the table has no `schedule`; a `schedule` key defaults to `"cron"` instead |
| `repository` | *(required)* | Alias of a `[repositories.<alias>]` entry |
| `checkout` | `"worktree"` | `"worktree"` or `"main"` (shared checkout, not a branch name) |
| `prompt` | *(required)* | Non-empty `string.Template` with `${placeholders}` |
| `profile` | `None` | Named CLI profile; otherwise `agents.defaults.profile`, which defaults to `"opencode"`. See [Providers and agents](providers.md) for profile options |

### Shared GitHub filters

Compiled into the Search query by `src/curupira/clients/github_search.py`.

| Field | Default | Search qualifier / behavior |
| --- | --- | --- |
| `repo` | *(required)* | `repo:owner/name` (`owner/repository` format) |
| `state` | `"open"` | `"open"` → `is:open`; `"closed"` → `is:closed`; `"all"` → neither. For pull requests, `is:closed` includes merged PRs |
| `labels` | `()` | Each value → `label:…` (AND: every label must be present) |
| `exclude_labels` | `()` | Each value → `-label:…` |
| `assignee` | `None` | Login, `@me`, `none` → `no:assignee`, or `any` → `assignee:*` |
| `author` | `None` | `author:…` |
| `milestone` | `None` | `milestone:…` |
| `project` | `None` | Passed through verbatim as `project:<value>`; see [Searching issues and pull requests](https://docs.github.com/en/search-github/searching-on-github/searching-issues-and-pull-requests) for GitHub's `project:` qualifier |
| `sort` | `"created-asc"` | Appended as `sort:…`. Allowed: `created-asc`, `created-desc`, `updated-asc`, `updated-desc`, `comments-asc`, `comments-desc` |

Values with whitespace or `"`, `:`, `,` are quoted in the compiled query.

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

Under `[settings.polling]` (`PollingSettings`):

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

Discovery uses GraphQL Search (`ISSUE` search type covers both issues and pull requests)
over `httpx`. There is no free-form `query` field: filters are typed TOML only.

### Deduplication

`PollingTaskFeed` keeps an in-memory (per process) set of task identity keys
(`[automation_id, repo, task_type, id]`). After a task is admitted, later polls in that
process skip it for that automation. The set is not persisted: after a restart, an item that
still matches the filters is discovered again. Deduplication is per automation, so two
automations may process the same issue or pull request with different prompts.
`run --dry-run` previews without adding to the seen set.

When a full cycle finds nothing (or discovery fails), the feed waits
`poll_interval_seconds`, then doubles the wait on consecutive empty cycles up to five
minutes (`300` seconds). Any successful discovery resets the interval.

## What the agent prompt receives

Placeholders use `${name}` syntax and are validated when the configuration loads. Unknown
placeholders are rejected.

**Common fields** (`COMMON_PROMPT_FIELDS`): `${repo}`, `${repository}`,
`${automation_id}`, `${task_type}`, `${task_number}`, `${task_title}`, `${task_body}`,
`${task_url}`. `${repo}` is the forge identity; `${repository}` is the checkout alias.
`${task_body}` is filled from the item's `*_body` field.

**Issues** (`IssueItem`): `${issue_number}`, `${issue_title}`, `${issue_body}`,
`${issue_url}`.

**Pull requests** (`PullRequestItem`): `${pull_request_number}`, `${pull_request_title}`,
`${pull_request_body}`, `${pull_request_url}`, `${pull_request_is_draft}`,
`${pull_request_head_ref}`, `${pull_request_base_ref}`.

Booleans render as `true` / `false`; missing optional values render as empty strings.

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
