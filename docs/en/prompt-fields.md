---
render_macros: false
---

# Prompt field reference

These are the names you can use in a prompt, either as `${name}` or as `{{ name }}` (see
[Writing prompts](prompts.md)). Run `curupira validate` to check that the names you use exist.

Types are what you see in Jinja: text, numbers, booleans (`true`/`false`), and lists. With `${name}`
a list is inserted as JSON, for example `["bug","security"]`.

## Every automation

| Field | Type | Meaning |
| --- | --- | --- |
| `repo` | text | The GitHub repository `owner/name` (the one the item belongs to). For cron, the identity of `repository` |
| `repository` | text | The checkout alias from `[repositories.<alias>]` |
| `automation_id` | text | The automation name, `[automations.<name>]` |
| `automation` | text | Same as `automation_id` |
| `task_type` | text | The trigger, for example `plugins-py/github-issues` or `cron` |
| `task_number` | text | The item id. For cron, the scheduled time as a Unix timestamp |
| `task_title` | text | The item title (the automation name for cron) |
| `task_body` | text | The item body, when the trigger has one |
| `task_url` | text | The item URL (`cron://<name>` for cron) |

## Issues (`github-issues`)

| Field | Type | Meaning |
| --- | --- | --- |
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
| `issue_created_at`, `issue_updated_at` | text | ISO timestamps, for example `2026-10-01T12:00:00Z` |
| `issue_linked_pull_requests` | list | URLs of pull requests that will close the issue |
| `issue_comment_count` | number | Total number of comments |
| `issue_comments` | text (JSON) | The latest 10 comments. Use `issue_comments \| fromjson` to loop over `author` and `body` |

## Pull requests (`github-pull-requests`)

| Field | Type | Meaning |
| --- | --- | --- |
| `pull_request_number` | number | Pull request number |
| `pull_request_title`, `pull_request_body`, `pull_request_url` | text | Title, description, web URL |
| `pull_request_author` | text | Login of the author, for example `app/dependabot` |
| `pull_request_labels` | list | Label names |
| `pull_request_assignees` | list | Assignee logins |
| `pull_request_requested_reviewers` | list | Logins or team names asked to review |
| `pull_request_milestone` | text | Milestone title, or empty |
| `pull_request_created_at`, `pull_request_updated_at` | text | ISO timestamps |
| `pull_request_head_ref`, `pull_request_base_ref` | text | Source and target branch names |
| `pull_request_head_sha` | text | Commit id of the head |
| `pull_request_is_draft` | boolean | Draft pull request |
| `pull_request_mergeable` | text | `MERGEABLE`, `CONFLICTING`, or `UNKNOWN` |
| `pull_request_merge_state_status` | text | `CLEAN`, `BLOCKED`, `BEHIND`, `DIRTY`, `DRAFT`, `HAS_HOOKS`, `UNSTABLE`, `UNKNOWN` |
| `pull_request_review_decision` | text | `APPROVED`, `CHANGES_REQUESTED`, `REVIEW_REQUIRED`, or empty when no review is required |
| `pull_request_ci_status` | text | State of the checks on the head commit: `SUCCESS`, `FAILURE`, `PENDING`, `ERROR`, `EXPECTED`, or empty when none ran |
| `pull_request_changed_files`, `pull_request_additions`, `pull_request_deletions` | number | Size of the change |
| `pull_request_closing_issues` | list | URLs of the issues the pull request closes |
| `pull_request_comment_count` | number | Total number of comments |
| `pull_request_comments` | text (JSON) | The latest 10 comments, like `issue_comments` |

## Project items (`github-project-items`) { #project-items }

Issues and pull requests share the `item_*` names, so one prompt works for both.

| Field | Type | Meaning |
| --- | --- | --- |
| `item_type` | text | `issue` or `pull_request` |
| `item_number`, `item_title`, `item_body`, `item_url`, `item_state` | text or number | Same meaning as for issues |
| `item_author` | text | Login of the author |
| `item_labels`, `item_assignees` | list | Label names and assignee logins |
| `item_milestone` | text | Milestone title, or empty |
| `item_created_at`, `item_updated_at` | text | ISO timestamps |
| `item_comment_count`, `item_comments` | number, text (JSON) | As for issues |
| `project_title`, `project_url` | text | The board |
| `project_column` | text | The column (value of `status_field`) the item was found in |
| `project_fields` | text (JSON) | All field values of the card, for example `{"Status": "Ready", "Priority": "P1"}`. Use `project_fields \| fromjson` |
| `pull_request_head_ref`, `pull_request_base_ref`, `pull_request_head_sha` | text | Only for pull requests, empty otherwise |
| `pull_request_is_draft` | boolean | Only meaningful for pull requests |
| `pull_request_review_decision`, `pull_request_ci_status` | text | Only for pull requests, empty otherwise |

## Optional values

A field that has no value for the item is **empty text** (for example the milestone of an issue
without one), so `{{ issue_milestone or "none" }}` works. A field that does not apply to the item at
all (for example `pull_request_head_ref` for an issue in a project) is empty as well.
