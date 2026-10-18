# Curupira

Curupira runs automations on your machine. It watches a source of work (GitHub issues, pull
requests, a GitHub Project board column, or a cron schedule), and hands each item to a
coding-agent CLI you already use, such as Claude Code, Codex, Gemini, or OpenCode. Each
task runs in its own Git worktree, so your own checkout is never touched.

Everything is configured in one TOML file, `~/.curupira/settings.toml`.

## Quick start (about 5 minutes) { #quick-start }

You need [Git](https://git-scm.com/), the [GitHub CLI](https://cli.github.com/) (`gh`), and one
coding-agent CLI. Details are in [Installation](installation.md).

**1. Install and sign in**

```sh
uv tool install 'curupira[github]'
gh auth login
```

**2. Create `~/.curupira/settings.toml`**

This resolves issues that carry the label `agent-ready`:

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"   # where the agent works

[agents.defaults]
profile = "claude"
timezone = "UTC"

[agents.profiles.claude]
provider = "claude"

[plugins.plugins-py]                          # the official GitHub triggers
type = "uvx"
args = ["--from", "curupira-plugins", "curupira-plugins"]

[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"
repository = "api"
repo = "acme/api"                             # the GitHub repository to watch
labels = ["agent-ready"]
prompt = """
Resolve issue #${issue_number}: ${issue_title}

${issue_body}
"""
```

**3. Check it, preview it, run it**

```sh
curupira validate      # is the file correct?
curupira run --dry-run # which task would run, and the exact prompt the agent gets
curupira run --watch   # keep polling and run tasks as they appear
```

`--dry-run` clones nothing and starts no agent, so it is safe to repeat while you tune
filters and the prompt.

## Where to go next

| I want to... | Read |
| --- | --- |
| Install Curupira and the agent CLIs | [Installation](installation.md) |
| Understand every setting in the file | [Configuration](configuration.md) |
| Pick a trigger and see a minimal example | [Automations](automations.md) |
| Filter issues and pull requests | [GitHub issues and pull requests](github.md) |
| Work from a project board column | [GitHub Projects](github-projects.md) |
| Write a smarter prompt (conditions, loops) | [Writing prompts](prompts.md) |
| See every field a prompt can use | [Prompt field reference](prompt-fields.md) |
| Copy a working setup | [Recipes](recipes.md) |
| Choose or tune the coding agent | [Providers and agents](providers.md) |
| Run it day to day, read logs, fix errors | [Operations](operations.md) |
