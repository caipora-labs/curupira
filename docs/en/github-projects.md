---
render_macros: false
---

# GitHub Projects (board columns)

`plugins-py/github-project-items` turns a column of a GitHub Projects board into a work queue.
Move a card to the column you chose, and Curupira hands that issue or pull request to your
coding agent. It works with user and organization projects (the new "Projects", also called
Projects v2).

```toml
[automations.work-ready-column]
trigger_type = "plugins-py/github-project-items"
repository = "api"          # checkout alias where the agent runs
owner = "acme"              # user or organization that owns the project
project = 5                 # the number in the project URL
column = "Ready"            # a value of the Status field
prompt = """
{% if item_type == "pull_request" %}Review{% else %}Resolve{% endif %} #${item_number}: ${item_title}

${item_body}
"""
```

## Before you start

1. Sign in with the GitHub CLI and add the project scope. Without `read:project` GitHub
   reports that the project does not exist.

   ```sh
   gh auth login
   gh auth refresh -s read:project
   ```

2. Find the **project number**. It is the number at the end of the project URL:
   `https://github.com/orgs/acme/projects/5` is project `5` of owner `acme`. You can also list
   them:

   ```sh
   gh project list --owner acme        # the first column is the number
   gh project list --owner @me         # your personal projects
   ```

3. Find the exact **column names**. They are the options of the `Status` field:

   ```sh
   gh project field-list 5 --owner acme
   ```

## Fields

| Field | Default | Meaning |
| --- | --- | --- |
| `owner` | *(required)* | User or organization login that owns the project |
| `project` | *(required)* | Project number |
| `column` | *(required)* | One column name or a list. Not case-sensitive |
| `status_field` | `"Status"` | The single-select field that holds the column. Change it if your board uses another field, for example `"Stage"` |
| `content` | `"all"` | `"issue"`, `"pull_request"`, or `"all"` |
| `repo` | none | Only items from this `owner/name`. Projects often span many repositories |
| `state` | `"open"` | `"open"`, `"closed"`, or `"all"` |
| `labels` | none | Every listed label must be on the item |
| `exclude_labels` | none | None of the listed labels may be on the item |
| `assignee` | none | A login, `"none"` (unassigned), or `"any"` (assigned to someone) |
| `author` | none | The login of the author |

Draft cards (notes that are not yet issues) and archived cards are always skipped, because
they have no repository to work in.

!!! note "Closed items"
    `state` defaults to `"open"`, so a closed issue that is still sitting in a column is
    ignored. Use `state = "all"` if you want the column to be the only rule.

## Which repository does the agent work in?

A board can hold items from several repositories, but each automation runs in one checkout,
the `repository` alias. Two common setups:

- **One repository per board.** Set `repo = "acme/api"` and `repository = "api"`.
- **Several repositories.** Create one automation per repository, each with its own `repo`
  and `repository`, all pointing at the same project and column.

In the prompt, `${repo}` is always the repository of the matched item, which is useful for
`gh` commands.

## A column-driven workflow

Use one column per stage and one automation per stage. Agents move from one to the next when
you (or a later automation) move the card:

| Column | Automation | What the agent does |
| --- | --- | --- |
| `Ready` | `column = "Ready"` | Implements the issue and opens a pull request |
| `Review` | `column = "Review"`, `content = "pull_request"` | Reviews the pull request and comments |

Each item is handled once: when the agent finishes successfully, that issue or pull request
is remembered and is not run again by the same automation, even if you drag the card back into
the column. See [Deduplication](github.md#deduplication). Cards whose agent run failed are tried
again after a restart.

## What the prompt can use

Project items expose `${item_*}`, `${project_*}` and a few `${pull_request_*}` fields. See
the [Prompt field reference](prompt-fields.md#project-items). The
column the item was found in is `${project_column}`, and every field of the card (for example
`Priority` or `Iteration`) is in `${project_fields}` as JSON:

```toml
prompt = """
{% set fields = project_fields | fromjson %}
Priority: {{ fields.Priority | default("none") }}
"""
```

## Troubleshooting

| Message or symptom | Cause and fix |
| --- | --- |
| `GitHub project 5 not found for 'acme'` | Wrong owner or number, or the token lacks `read:project`. Run `gh auth refresh -s read:project` and check the URL |
| Nothing is found, but the column has cards | The cards are closed (`state = "all"`), are drafts, belong to another `repo`, or the column name differs. Compare with `gh project field-list` |
| A custom `status_field` finds nothing | Use the exact field name, for example `status_field = "Stage"` |
| `column: Value error` from `validate` | `column` is empty. Give at least one name |
