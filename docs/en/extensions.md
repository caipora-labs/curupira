# Build extensions

An extension is a **task source**: a small program that tells Curupira what work exists.
The [connectors](plugins.md) (GitHub today, Monday.com and Azure DevOps in development) are
extensions, and you can write your own for Jira, Linear, a database queue, or anything else
that can produce one item at a time.

Extensions run as **separate processes**. Curupira starts them with `uvx` or `npx` and
talks to them over stdin and stdout with a small
[JSON-RPC protocol](extensions-protocol.md). They never run inside the Curupira process,
and no FFI is involved.

<div class="grid cards" markdown>

-   :material-language-python:{ .lg } **Python SDK**

    ---

    `curupira-sdk`: decorate a function, return one object. Stdlib-only, Pydantic optional.

    [Write a Python extension](extensions-python.md)

-   :material-language-javascript:{ .lg } **JavaScript and TypeScript SDK**

    ---

    `@caipora/curupira-sdk`: `defineTriggers` and an npm `bin`, launched with `npx`.

    [Write a Node.js extension](extensions-javascript.md)

-   :material-file-document-outline:{ .lg } **Manifest and protocol**

    ---

    Framing, methods, results, error codes, and the `curupira-extension.toml` manifest.

    [Read the reference](extensions-protocol.md)

</div>

## What an extension does { #responsibilities }

| An extension... | Curupira (the host)... |
| --- | --- |
| Declares its triggers and the settings each one accepts | Reads the TOML and passes each automation's settings |
| Validates those settings | Reports validation errors from `curupira validate` |
| Returns the **next item** as a flat list of key/value pairs, or nothing | Deduplicates, schedules, and limits concurrency |
| Hears when a task starts and when it finishes | Clones, creates worktrees, runs `setup_script` |
| Writes logs to stderr | Renders the prompt and starts the coding agent |

Extensions must not choose a coding agent, build agent command lines, clone repositories,
or manage worktrees. Coding agents are built into the host; supporting a new agent is a
change to Curupira itself.

## Register an extension { #register }

Every extension is registered in `settings.toml` under an alias of your choice, with the
launcher and its arguments. Automations then address a trigger as `<alias>/<trigger>`.

=== "Python (uvx)"

    ```toml
    [plugins.acme]
    type = "uvx"
    args = ["--from", "acme-curupira==1.2.0", "acme-curupira"]
    tools = ["*"]

    [automations.triage]
    trigger_type = "acme/tickets"
    repository = "api"
    prompt = "Triage ${title}"
    ```

=== "Node.js (npx)"

    ```toml
    [plugins.acme]
    type = "npx"
    args = ["--yes", "@acme/curupira-ext@1.2.0"]
    tools = ["*"]

    [automations.triage]
    trigger_type = "acme/tickets"
    repository = "api"
    prompt = "Triage ${title}"
    ```

`args` are passed as separate arguments, never through a shell. Pin a version so every
machine runs the same code. `tools` keeps only matching triggers (`github-*`) or drops
them (`!github-project-*`).

## Inspect plugins { #manage }

`curupira plugins` lists the triggers you can use and the settings each one accepts:

```sh
curupira plugins list
curupira plugins info curupira-plugins
```

`plugins list` also shows built-in cron and the built-in coding-agent providers (labelled
`agent:<name>` with origin `built-in`). Listing reads `curupira-extension.toml` manifests
and **never executes extension code**.

### Runtime requirements { #runtime-requirements }

| Source | Needs on `PATH` |
| --- | --- |
| `type = "uvx"` plugins | `uvx` (from [uv](https://docs.astral.sh/uv/)) |
| `type = "npx"` plugins | `npx` (Node.js 20+) |
| Built-in cron and coding agents | the agent CLIs you configure, plus `git` |

If a launcher is missing, `curupira validate` says which one.

## Security { #security }

Third-party extensions run with your user privileges. A subprocess is not a sandbox.
Install only packages you trust, and pin their versions. Curupira never installs packages
while it lists plugins.

The text an extension returns usually comes from people outside your team (issue titles,
comments). It ends up in a prompt; read
[task text is untrusted](github.md#security) before you automate public sources.
