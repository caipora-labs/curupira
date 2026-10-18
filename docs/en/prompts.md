---
render_macros: false
---

# Writing prompts

The `prompt` of an automation is the text your coding agent receives. You write it in
`settings.toml`; Curupira fills in the details of each task before the agent starts.

Start simple, and add logic only when you need it.

## 1. Insert fields with `${name}`

```toml
prompt = "Resolve issue ${issue_number}: ${issue_title}\n\n${issue_body}"
```

Use a multi-line string for longer prompts. In TOML, `"""` strings process escapes such as
`\n`; `'''` strings are taken literally:

```toml
prompt = """
Resolve issue ${issue_number} in ${repo}.

${issue_body}
"""
```

Lists (such as labels) are inserted as JSON, for example `["bug","security"]`.

## 2. Make it dynamic

For anything beyond inserting values, use Jinja syntax. You can mix it freely with `${name}`.

| You want | Write |
| --- | --- |
| A value | `{{ issue_title }}` |
| A fallback for an empty or optional value | `{{ issue_milestone \| default("none") }}` |
| Text only in some cases | `{% if "security" in issue_labels %}...{% endif %}` |
| Two alternatives | `{% if item_type == "pull_request" %}...{% else %}...{% endif %}` |
| Repeat for each item of a list | `{% for label in issue_labels %}- {{ label }}\n{% endfor %}` |
| Shorten long text | `{{ issue_body \| truncate(2000) }}` |
| Loop over the latest comments | `{% for c in issue_comments \| fromjson %}{{ c.author }}: {{ c.body }}{% endfor %}` |

Example, one automation that adapts to what it receives (more in [Recipes](recipes.md)):

```toml
[automations.work-ready-column]
trigger_type = "plugins-py/github-project-items"
repository = "api"
owner = "acme"
project = 5
column = ["Ready"]
prompt = """
{% if item_type == "pull_request" %}
Review pull request #{{ item_number }} ({{ pull_request_head_ref }} -> {{ pull_request_base_ref }}).
CI is {{ pull_request_ci_status | default("unknown") }}.
{% else %}
Resolve issue #{{ item_number }}: {{ item_title }}
{% endif %}

{% if "security" in item_labels %}
This is a security issue. Keep the change minimal and explain the risk in the commit message.
{% endif %}

${item_body}
"""
```

Notes:

- The line break after a `{% ... %}` tag is kept, so a block on its own line leaves a blank
  line. Use `{%- ... -%}` to trim the whitespace around a tag when that matters.
- Jinja has many more [built-in filters and tests](https://docs.rs/minijinja/latest/minijinja/filters/index.html)
  (`upper`, `join`, `length`, `first`, `selectattr`, ...).

## Fields

Every automation gets these:

`${repo}` (the GitHub `owner/name`), `${repository}` (the checkout alias), `${automation_id}`
(also `${automation}`), `${task_type}`, `${task_number}`, `${task_title}`, `${task_body}`,
`${task_url}`. For cron tasks `${task_number}` is the scheduled time.

Each trigger adds its own fields. The full list is in the [Prompt field reference](prompt-fields.md),
and [Recipes](recipes.md) has complete automations to copy.

## Checking your prompt

1. `curupira --config settings.toml validate` checks syntax and that every field you use
   exists. A typo gets a suggestion:

   ```text
   automation "work-ready-column": prompt uses unknown field(s) "item_titel"
   (did you mean "item_title"?). Available fields: ...
   ```

2. `curupira --config settings.toml run --dry-run` finds one matching task and prints the final
   prompt, without cloning or starting an agent. This is the quickest way to see what the
   agent will get.

A field that exists but has no value for a given task (for example a pull-request field on
an issue) is an error when the task runs, not an empty string. Guard it with `default("")` or
an `{% if %}`.

## Security

Titles, bodies, and comments come from other people. Their text is inserted as plain text
and is never interpreted as a template, so `{{ ... }}` inside an issue body does nothing. It can
still try to steer the agent, so follow the advice in
[the security notes](github.md#security).
