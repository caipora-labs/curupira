# GitHub Copilot CLI

Curupira runs `copilot` non-interactively with JSONL output, a persisted session ID, and
`--no-ask-user`. The CLI exits after the prompt completes. Curupira currently returns the
captured JSONL unchanged because the event schema for programmatic prompt runs is not
documented; it does not yet extract a final assistant message.

## Installation

Install `@github/copilot` with npm (`npm install -g @github/copilot`), use
`brew install copilot-cli` on Homebrew, or use `winget install GitHub.Copilot` on Windows.

See the [official installation guide](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)
for prerequisites and platform-specific details.

## Authentication

Authenticate with `copilot login`, or provide a supported token in the environment. Token
precedence is `COPILOT_GITHUB_TOKEN`, then `GH_TOKEN`, then `GITHUB_TOKEN`. Classic `ghp_`
personal access tokens are not supported by Copilot CLI.

If `GH_TOKEN` is already exported for GitHub CLI, Copilot picks it up before
`GITHUB_TOKEN`; ensure that token has Copilot access. Curupira does not manage or forward
authentication credentials.

## Profile options

| Profile option | Native argument |
| --- | --- |
| Task message | `--prompt=<message>`; the equals form preserves a leading dash in the prompt |
| Session | `--session-id=<id>` for both new and resumed runs; Curupira assigns the new UUID |
| Output | `--output-format=json`; Curupira preserves the captured JSONL unchanged |
| User questions | `--no-ask-user`, always enabled by Curupira |
| `model` | `--model=<model>` (`auto` is accepted by Copilot CLI) |
| `agent` | `--agent=<agent>` for a configured custom agent |
| `effort` | `--reasoning-effort=<level>`: `low`, `medium`, `high`, `xhigh`, or `max` |
| `allow_all_tools` | `--allow-all-tools` |
| `allow_tools` | One `--allow-tool=<comma-separated-patterns>` argument |
| `deny_tools` | One `--deny-tool=<comma-separated-patterns>` argument; deny rules win over allow rules |

Curupira always passes `--no-ask-user`: Copilot cannot stop to ask a question while a task
is running unattended. Each run also passes `--output-format=json` and
`--session-id=<id>`. New runs use the UUID Curupira persisted before launching the CLI;
resumed runs pass their persisted session ID with the same flag. No separate `--resume`
flag is used. The task prompt is passed as `--prompt=<message>` so a leading dash remains
part of the prompt.

### Headless tool permissions

Headless tool use needs explicit authorization. Set `allow_all_tools = true` to permit
every tool supported by Copilot CLI, or set `allow_tools` to explicitly permit selected
tools and patterns such as `shell(git:*)` and `write`. `deny_tools` can explicitly deny
tools; denies take precedence over allows. Tool entries cannot contain commas because
Curupira passes each list as one comma-separated CLI argument.

Curupira never adds broader flags such as `--allow-all`, `--yolo`, or path/URL bypasses.

## Configuration reference

::: curupira.agents.copilot.CopilotCliProfile
    options:
      inherited_members:
        - model
      members:
        - model

### Inherited `model` field

The common CLI profile supplies `model`; Copilot maps it to `--model=<model>`.
