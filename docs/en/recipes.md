---
render_macros: false
---

# Recipes

Copy one, change the repository names, and run `curupira validate` followed by
`curupira run --dry-run`. Every recipe assumes the settings from the
[quick start](index.md#quick-start) (a repository alias, an agent profile, and
the `[plugins.plugins-py]` registration).

## Resolve issues that carry a label

```toml
[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
exclude_labels = ["blocked"]
linked_pull_request = false          # skip issues that already have a pull request
prompt = """
Resolve issue #${issue_number}: ${issue_title}

${issue_body}

Open a pull request when you are done.
"""
```

## Review pull requests that are ready

Only pull requests that are not drafts, have no conflicts, and have passing checks.

```toml
[automations.review-pull-requests]
trigger_type = "plugins-py/github-pull-requests"
repository = "api"
repo = "acme/api"
draft = false
mergeable = true
ci_status = "success"
labels = ["review-needed"]
prompt = """
Review pull request #${pull_request_number}: ${pull_request_title}
Branch: ${pull_request_head_ref} -> ${pull_request_base_ref}
Changed files: ${pull_request_changed_files} (+${pull_request_additions} -${pull_request_deletions})

${pull_request_body}
"""
```

## Merge Dependabot updates

```toml
[automations.merge-dependabot]
trigger_type = "plugins-py/github-pull-requests"
repository = "api"
repo = "acme/api"
author = "app/dependabot"
draft = false
mergeable = true
prompt = """
Analyze Dependabot pull request #${pull_request_number} (${pull_request_title}) in ${repo}.
Fix what the update breaks, wait for the checks, then squash-merge with
`gh pr merge ${pull_request_number} --repo ${repo} --squash`.
"""
```

The agent profile needs `auto_approve = true` so that unattended `gh` writes do not stop for
approval. See [Providers and agents](providers.md).

## Address review feedback

Pick up pull requests where a reviewer asked for changes and show the agent the conversation.

```toml
[automations.address-feedback]
trigger_type = "plugins-py/github-pull-requests"
repository = "api"
repo = "acme/api"
review = "changes_requested"
draft = false
prompt = """
Pull request #${pull_request_number} needs changes: ${pull_request_title}

Latest comments:
{% for c in pull_request_comments | fromjson %}
- {{ c.author }}: {{ c.body | truncate(400) }}
{% endfor %}

Make the requested changes on branch ${pull_request_head_ref}.
"""
```

## Work from a board column

One automation handles both issues and pull requests that sit in the `Ready` column.

```toml
[automations.board-ready]
trigger_type = "plugins-py/github-project-items"
repository = "api"
owner = "acme"
project = 5
column = "Ready"
repo = "acme/api"
prompt = """
{% if item_type == "pull_request" %}
Review pull request #{{ item_number }} ({{ pull_request_head_ref }} -> {{ pull_request_base_ref }}).
{% else %}
Resolve issue #{{ item_number }}: {{ item_title }}
{% endif %}

${item_body}
"""
```

## Adapt the prompt to labels

```toml
[automations.triage]
trigger_type = "plugins-py/github-issues"
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
prompt = """
Resolve issue #${issue_number}: ${issue_title}

{% if "security" in issue_labels %}
This issue is security related. Keep the change minimal and describe the risk in the commit message.
{% elif "bug" in issue_labels %}
This is a bug. Write a failing test first, then fix it.
{% else %}
Implement the request and add tests.
{% endif %}

${issue_body}
"""
```

## Use the card priority from a board

```toml
[automations.prioritized]
trigger_type = "plugins-py/github-project-items"
repository = "api"
owner = "acme"
project = 5
column = ["Ready"]
prompt = """
{% set card = project_fields | fromjson %}
Priority: {{ card.Priority | default("not set") }}

Resolve #${item_number}: ${item_title}

${item_body}
"""
```

## A weekly maintenance task (no GitHub)

```toml
[automations.weekly-maintenance]
trigger_type = "cron"
repository = "api"
schedule = "0 9 * * 1"        # every Monday at 09:00 in the configured timezone
prompt = """
Check dependencies and the CI configuration of ${repository}. Open a pull request with any
safe updates. Run number: ${task_number}.
"""
```
