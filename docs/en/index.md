---
template: home.html
title: Curupira
description: Hand tasks from GitHub, project boards, and cron schedules to the coding-agent CLI you already use.
hide:
  - navigation
  - toc
hero:
  eyebrow: Local automations for coding agents
  title: Hand your backlog to the coding agent you already use
  lead: >-
    Curupira watches task sources through connectors (GitHub today, Monday.com and
    Azure DevOps in development) and cron schedules, then runs each task with Claude
    Code, Codex, Gemini, or another agent CLI in its own Git worktree. It runs on your
    machine, from one TOML file.
  primary:
    text: Get started
    href: quick-start/
  secondary:
    text: How it works
    href: concepts/
  install_label: Install
  trace_label: Example terminal session
  trace_caption: >-
    Validate the file, preview the exact prompt, then keep watching. Each finished task
    prints ok with its identity and is never run twice.
---

<div class="grid cards cp-cols-4" markdown>

-   :material-rocket-launch-outline:{ .lg } **Get started**

    ---

    Install the CLI, write a first automation, and see the prompt before anything runs.

    [Quick start](quick-start.md) · [Installation](installation.md)

-   :material-transit-connection-variant:{ .lg } **Orchestrator**

    ---

    Configure repositories, agent profiles, automations, prompts, and the run loop.

    [Configuration](configuration.md) · [Running Curupira](operations.md)

-   :material-puzzle-outline:{ .lg } **Plugins and connectors**

    ---

    Task sources for GitHub and more. Each connector is a plugin you register by name.

    [Plugins overview](plugins.md) · [Recipes](recipes.md)

-   :material-code-braces:{ .lg } **Build extensions**

    ---

    Write your own connector in Python or JavaScript with the Curupira SDKs.

    [Extensions overview](extensions.md) · [Protocol](extensions-protocol.md)

</div>

## Connectors { #connectors }

A connector is a plugin that tells Curupira what work exists. Pick one, register it in
`settings.toml`, and every task it finds goes to your agent.

<div class="grid cards cp-cols-4" markdown>

-   :material-github:{ .lg } **GitHub** <span class="cp-status cp-status--live">Available</span>

    ---

    Issues, pull requests, and Project board columns, through the `gh` CLI.

    [GitHub connector](github.md)

-   :material-view-dashboard-outline:{ .lg } **Monday.com** <span class="cp-status cp-status--dev">In development</span>

    ---

    Items from your Monday.com boards as tasks for the agent.

    [Plugins overview](plugins.md#catalog)

-   :material-microsoft-azure-devops:{ .lg } **Azure DevOps** <span class="cp-status cp-status--dev">In development</span>

    ---

    Work items from Azure DevOps as tasks for the agent.

    [Plugins overview](plugins.md#catalog)

-   :material-puzzle-plus-outline:{ .lg } **Your own** <span class="cp-status cp-status--live">Available</span>

    ---

    Anything that can return one item at a time can be a connector.

    [Build extensions](extensions.md)

</div>

Cron is built in and needs no connector: [schedule an automation](automations.md#cron).

## Works with your agent CLI { #agents }

Curupira starts each agent through its own non-interactive command, so your login,
models, and settings stay where they are.

<div class="cp-agents" markdown>

- [Claude Code](providers/claude.md)
- [Codex](providers/codex.md)
- [Cursor](providers/cursor.md)
- [Gemini CLI](providers/gemini.md)
- [GitHub Copilot CLI](providers/copilot.md)
- [Kilo CLI](providers/kilo.md)
- [OpenCode](providers/opencode.md)
- [pi](providers/pi.md)
- [Qwen Code](providers/qwen.md)

</div>

## Common tasks { #tasks }

<div class="cp-tasks" markdown>

- [Installation](installation.md) <span>Install Curupira and the agent CLIs</span>
- [How it works](concepts.md) <span>Follow a task from its source to the agent</span>
- [Configuration](configuration.md) <span>Understand every setting in the file</span>
- [Automations](automations.md) <span>Pick a trigger and see a minimal example</span>
- [GitHub connector](github.md) <span>Filter issues and pull requests</span>
- [GitHub Projects](github-projects.md) <span>Work from a project board column</span>
- [Writing prompts](prompts.md) <span>Use conditions and loops in a prompt</span>
- [Prompt field reference](prompt-fields.md) <span>See every field a prompt can use</span>
- [Recipes](recipes.md) <span>Copy a working setup</span>
- [Coding agents](providers.md) <span>Choose or tune the coding agent</span>
- [Running Curupira](operations.md) <span>Run it day to day and fix errors</span>
- [Build extensions](extensions.md) <span>Write your own connector</span>

</div>
