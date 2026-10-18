# Quick start

This page takes about five minutes. At the end, Curupira watches one repository and hands
every issue labelled `agent-ready` to Claude Code. Swap the agent or the label for your own.

You need [Git](https://git-scm.com/), the [GitHub CLI](https://cli.github.com/) (`gh`), and
one coding-agent CLI that is already signed in. [Installation](installation.md) covers every
platform and option.

## 1. Install and sign in

=== "uv"

    ```sh
    uv tool install curupira
    gh auth login
    ```

=== "pip"

    ```sh
    pip install curupira
    gh auth login
    ```

=== "npm"

    ```sh
    npm install -g @caipora-labs/curupira
    gh auth login
    ```

The GitHub connector is a [plugin](plugins.md) that Curupira starts through `uvx`, so you
also need [uv](https://docs.astral.sh/uv/) on `PATH`. Nothing else is installed up front.

## 2. Write `~/.curupira/settings.toml`

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"   # (1)!

[agents.defaults]
profile = "claude"
timezone = "UTC"

[agents.profiles.claude]
provider = "claude"                           # (2)!

[plugins.plugins-py]                          # (3)!
type = "uvx"
args = ["--from", "curupira-plugins", "curupira-plugins"]

[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"     # (4)!
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
prompt = """
Resolve issue #${issue_number}: ${issue_title}

${issue_body}
"""
```

1.  Where the agent works. Curupira clones it once and gives each task its own worktree.
2.  Any [supported agent](providers.md): `codex`, `gemini`, `opencode`, and more.
3.  Registers the GitHub connector under the alias `plugins-py`. Other connectors are
    registered the same way.
4.  `<alias>/<trigger>`: the issues trigger from the connector registered above. `repo` and
    `labels` are its filters, and `${issue_number}` and the other fields fill the prompt.

## 3. Check it, preview it, run it

```sh
curupira validate      # is the file correct?
curupira run --dry-run # which task would run, and the exact prompt the agent gets
curupira run --watch   # keep polling and run tasks as they appear
```

!!! tip "Safe to repeat"
    `--dry-run` clones nothing and starts no agent. Use it while you tune filters and the
    prompt.

## Next steps

- [How it works](concepts.md): what happens between the issue and the agent.
- [Writing prompts](prompts.md): conditions, loops, and every field you can use.
- [Recipes](recipes.md): pull-request reviews, Dependabot, board columns, and cron.
- [Running Curupira](operations.md): output, exit codes, and sessions.
