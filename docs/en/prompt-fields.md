---
render_macros: false
---

# Prompt field reference

These are the names you can use in a prompt, either as `${name}` or as `{{ name }}` (see
[Writing prompts](prompts.md)). Run `curupira validate` to check that the names you use exist.

Every value is text (see [Every value is text](prompts.md#values-are-text)). Numbers, booleans
(`true`/`false`), and lists are shown in the *Type* column for what they mean; a list is JSON text,
for example `["bug","security"]`, that you open with `| fromjson`.

## Every automation

| Field | Type | Meaning |
| --- | --- | --- |
| `repository` | text | The GitHub repository `owner/name` of the automation's checkout (from the Git remote) |
| `automation` | text | The automation name, `[automations.<name>]` |

Cron prompts receive only these two.

## Issues (`github-issues`)

| Field | Type | Meaning |
| --- | --- | --- |
| `repo` | text | The repository `owner/name` the issue belongs to |
| `id`, `title`, `url` | text | Issue number, title, and web URL (same as the `issue_*` fields) |
| `issue_number` | number | Issue number |
| `issue_title` | text | Title |
| `issue_body` | text | Description (empty if none) |
| `issue_url` | text | Web URL |
| `issue_state` | text | `OPEN` or `CLOSED` |
| `issue_state_reason` | text | `COMPLETED`, `NOT_PLANNED`, `REOPENED`, or empty |
| `issue_author` | text | Login of the author |
| `issue_labels` | list | Label names |
| `issue_assignees` | list | Assignee logins |
| `issue_milestone` | text | Milestone title, or empty |
| `issue_created_at` | text | ISO timestamp, for example `2026-10-01T12:00:00Z` |

## Pull requests (`github-pull-requests`)

| Field | Type | Meaning |
| --- | --- | --- |
| `repo` | text | The repository `owner/name` the pull request belongs to |
| `id`, `title`, `url` | text | Pull request number, title, and web URL (same as the `pull_request_*` fields) |
| `pull_request_number` | number | Pull request number |
| `pull_request_title`, `pull_request_body`, `pull_request_url` | text | Title, description, web URL |
| `pull_request_author` | text | Login of the author, for example `app/dependabot` |
| `pull_request_labels` | list | Label names |
| `pull_request_assignees` | list | Assignee logins |
| `pull_request_milestone` | text | Milestone title, or empty |
| `pull_request_created_at` | text | ISO timestamp |
| `pull_request_head_ref`, `pull_request_base_ref` | text | Source and target branch names |
| `pull_request_head_sha` | text | Commit id of the head |
| `pull_request_is_draft` | boolean | Draft pull request |
| `pull_request_mergeable` | text | `MERGEABLE`, `CONFLICTING`, or `UNKNOWN` |
| `pull_request_merge_state_status` | text | `CLEAN`, `BLOCKED`, `BEHIND`, `DIRTY`, `DRAFT`, `HAS_HOOKS`, `UNSTABLE`, `UNKNOWN` |
| `pull_request_changed_files`, `pull_request_additions`, `pull_request_deletions` | number | Size of the change |
| `pull_request_closing_issues` | list | URLs of the issues the pull request closes |

## Project items (`github-project-items`) { #project-items }

Issues and pull requests share the `item_*` names, so one prompt works for both.

| Field | Type | Meaning |
| --- | --- | --- |
| `repo` | text | The repository `owner/name` the item belongs to |
| `id`, `title`, `url` | text | `owner/name#number`, the title, and the web URL |
| `item_type` | text | `issue` or `pull_request` |
| `item_number`, `item_title`, `item_body`, `item_url`, `item_state` | text or number | Same meaning as for issues |
| `item_author` | text | Login of the author |
| `item_labels`, `item_assignees` | list | Label names and assignee logins |
| `item_milestone` | text | Milestone title, or empty |
| `item_created_at` | text | ISO timestamp |
| `project_title`, `project_url` | text | The board |
| `project_column` | text | The column (value of `status_field`) the item was found in |
| `project_fields` | text (JSON) | All field values of the card, for example `{"Status": "Ready", "Priority": "P1"}`. Use `project_fields \| fromjson` |
| `pull_request_head_ref`, `pull_request_base_ref`, `pull_request_head_sha` | text | Only for pull requests, empty otherwise |
| `pull_request_is_draft` | boolean | Only meaningful for pull requests |

## Left out on purpose { #left-out-on-purpose }

Comments, update time, CI and review state, linked pull requests, and requested reviewers are
not fields. The host hashes every field a trigger returns into the task identity
([Deduplication](github.md#deduplication)), so a value that changes by itself, or because the
agent worked on the item, would start the same issue again. Ask the agent to read what it needs,
for example `gh issue view ${issue_number} --comments` or `gh pr checks ${pull_request_number}`.
The CI and review state can still be used to *select* pull requests with the `ci_status` and
`review` filters.

## Optional values

A field that has no value for the item is **empty text** (for example the milestone of an issue
without one), so `{{ issue_milestone or "none" }}` works. A field that does not apply to the item at
all (for example `pull_request_head_ref` for an issue in a project) is empty as well.
