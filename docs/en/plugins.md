# Plugins and connectors

A **plugin** is a program that tells Curupira what work exists. A **connector** is a plugin
for one tool you already work in, such as GitHub. Curupira starts the plugin, asks it for
the next item, and hands that item to your coding agent in its own Git worktree.

Connectors are not tied to one service. GitHub is the first one to ship, Monday.com and
Azure DevOps are in development, and you can [write your own](extensions.md).

## Connectors { #catalog }

<div class="grid cards" markdown>

-   :material-github:{ .lg } **GitHub** <span class="cp-status cp-status--live">Available</span>

    ---

    Issues, pull requests, and Project board columns, through the `gh` CLI. No token goes
    in your settings.

    [GitHub issues and pull requests](github.md) · [Projects](github-projects.md)

-   :material-view-dashboard-outline:{ .lg } **Monday.com** <span class="cp-status cp-status--dev">In development</span>

    ---

    Items from your Monday.com boards as tasks for the agent.

    Not released yet.

-   :material-microsoft-azure-devops:{ .lg } **Azure DevOps** <span class="cp-status cp-status--dev">In development</span>

    ---

    Work items from Azure DevOps as tasks for the agent.

    Not released yet.

-   :material-puzzle-plus-outline:{ .lg } **Your own** <span class="cp-status cp-status--live">Available</span>

    ---

    A connector for Jira, Linear, a database queue, or anything that can return one item
    at a time.

    [Build extensions](extensions.md)

</div>

Every connector works the same way for you: register it once, then point automations at
its triggers. Only the trigger names and their filters change.

The triggers that exist today:

| Trigger | Source | Needs |
| --- | --- | --- |
| [`plugins-py/github-issues`](github.md#minimal-issue-automation) | GitHub issues | `gh auth login` |
| [`plugins-py/github-pull-requests`](github.md) | GitHub pull requests | `gh auth login` |
| [`plugins-py/github-project-items`](github-projects.md) | GitHub Project board columns | `gh` with the `read:project` scope |
| [`cron`](automations.md#cron) | A local schedule, built into Curupira | Nothing |

## Register a connector { #register }

A plugin is registered under an alias you choose, together with the launcher that starts
it. Automations then address a trigger as `<alias>/<trigger>`.

```toml
[plugins.plugins-py]                                  # (1)!
type = "uvx"
args = ["--from", "curupira-plugins", "curupira-plugins"]

[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"             # (2)!
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
prompt = "Resolve issue #${issue_number}: ${issue_title}"
```

1.  The alias is yours to pick. `plugins-py` is the convention used across these docs for
    the official GitHub connector.
2.  `<alias>/<trigger>`: the trigger comes from the plugin registered above. The other keys
    are that trigger's filters.

The package runs through `uvx`, so you need [uv](https://docs.astral.sh/uv/) on `PATH`.
Plugins written for Node.js run through `npx` instead; see
[Register an extension](extensions.md#register).

=== "Pin a version"

    ```toml
    [plugins.plugins-py]
    type = "uvx"
    args = ["--from", "curupira-plugins==0.3.0", "curupira-plugins"]
    ```

    Every machine then runs the same plugin release.

=== "Keep some triggers"

    ```toml
    [plugins.plugins-py]
    type = "uvx"
    args = ["--from", "curupira-plugins", "curupira-plugins"]
    tools = ["github-*", "!github-project-*"]
    ```

    `tools` keeps matching triggers; a `!` pattern drops them.

## Use the GitHub connector { #github }

Sign in once. The connector calls `gh` with your account, so it sees exactly the
repositories and boards you can see.

```sh
gh auth login
gh auth refresh -s read:project   # only for Project board columns
```

See [Token scopes](github.md#prerequisites) for details, then choose a trigger:

<div class="grid cards" markdown>

-   :material-alert-circle-outline:{ .lg } **Issues**

    ---

    Labels, assignees, milestones, linked pull requests, and free search.

    [`github-issues`](github.md#minimal-issue-automation)

-   :material-source-pull:{ .lg } **Pull requests**

    ---

    Drafts, review state, CI status, authors such as Dependabot, and mergeability.

    [`github-pull-requests`](github.md)

-   :material-view-column-outline:{ .lg } **Project board columns**

    ---

    Cards in one column of a GitHub Project, with their custom fields.

    [`github-project-items`](github-projects.md)

-   :material-book-open-variant:{ .lg } **Recipes**

    ---

    Complete setups to copy: reviews, Dependabot, feedback, and boards.

    [Recipes](recipes.md)

</div>
