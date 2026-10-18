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

Titles and bodies from GitHub issues and pull requests are untrusted input. Curupira puts
them into the coding-agent prompt (`${issue_title}`, `${issue_body}`,
`${pull_request_title}`, `${pull_request_body}`, `${item_body}`). A hostile author can try to steer the agent. Restrict what reaches the
agent with `labels`, `author`, or `assignee`. Review what the agent profile is allowed to
run in the repository. Only run automations on repositories where you trust everyone who
can write text.

## First-use path

1. [Install Curupira](installation.md) and only the external CLIs your automations need
   (for example `gh`) plus the coding-agent CLI in
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
| Placeholder left unchanged in the prompt | `${name}` is not a host variable and the trigger did not return that key | Use a key the trigger returns; see the [Prompt field reference](prompt-fields.md). `validate` suggests the closest key |
| `prompt uses unknown field(s)` from `validate` | A `{{ name }}` (or a `${name}` that looks like a typo) is not a key of this trigger | Fix the name; the message lists the available fields |
| Prompt template error with a line number | Invalid Jinja syntax, for example an `if` block without its `endif` | Fix the line shown. To print literal double braces, use a `raw` block, see [Writing prompts](prompts.md#values-are-text) |
| `Required executable not found: gh` | CLI missing from `PATH` | Install and authenticate the CLI for that trigger |
| `schedule must be a valid five-field cron expression` | Six-field cron or invalid expression | Use five fields (`minute hour day-of-month month day-of-week`) |
| `repo must use the owner/repository format` | GitHub `repo` not `owner/name` | Use `acme/api`, not a URL |
| No tasks scheduled | Filters match nothing | Widen or drop labels / branch filters; empty cycles are not an error |
| `validate` exits `2` | TOML shape, unknown configuration keys, or prompt errors | Read the validation message; models reject unknown keys |

`curu validate` checks TOML shape, trigger configuration, and the prompt (syntax and field names)
without calling external APIs.
`curu run` and `curu run --watch` need the CLIs for your triggers
and the chosen agent CLI installed and authenticated.
