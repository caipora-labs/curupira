# Process extensions

Curupira's CLI is a Rust binary. **Task sources** (except built-in **cron**) run as
**separate processes** that speak the
[extension protocol](https://github.com/caipora-labs/curupira/blob/main/protocol/PROTOCOL.md)
(JSON-RPC 2.0 over length-prefixed stdin/stdout).

**Coding agents** (OpenCode, Claude Code, Codex, Cursor, Gemini CLI, GitHub Copilot CLI,
Kilo, pi, Qwen Code) are **built into the Rust core**. They are not process extensions
and do not use the extension protocol.

## Install the CLI

```bash
pip install curupira
# or
uv tool install curupira
```

`curupira` and `curu` are the same binary. Python is used only to distribute that
binary and the official **trigger** extension modules shipped in the wheel. Node.js is
required only when you install a Node-based third-party trigger extension.

## Manage extensions

```bash
curupira plugins list
curupira plugins info curupira-github
curupira plugins install --yes path:./plugins/curupira-github
curupira plugins install --yes pip:some-extension==1.2.3
curupira plugins install --yes npm:@acme/curupira-ext@1.2.3
curupira plugins uninstall some-extension
```

Discovery reads `curupira-extension.toml` manifests from
`~/.curupira/extensions/`, `CURUPIRA_EXTENSIONS_PATH`, and bundled `plugins/`.
**Listing never executes extension code.**

`plugins list` also shows built-in cron and the built-in coding-agent providers
(labeled `agent:<name>` with origin `built-in`).

### Runtime requirements

| Source | Needs on PATH |
| --- | --- |
| Official Python trigger extensions (shipped) | `python3` |
| `pip:` installs | `uvx` (from [uv](https://docs.astral.sh/uv/)) |
| `npm:` installs | `npx` (Node.js) |
| Built-in cron and coding agents | the agent CLIs you configure (plus `git`) |

## Official extensions

Bundled under `plugins/` and implemented in `python/curupira_official/`:

| Extension | Contributes |
| --- | --- |
| `curupira-github` | `github-issues`, `github-pull-requests` |
| `curupira-azure` | `azure-cli-pull-requests` |
| `curupira-trello` | `trello-cli-cards` |
| `curupira-monday` | `monday-items` |

**cron** and all coding-agent adapters remain inside the Rust CLI (not extensions).

## Write a Python extension

1. Depend on the framing rules in `protocol/PROTOCOL.md` (or the
   `curupira-extension` SDK under `plugins/sdk-python/`).
2. Implement `initialize`, `describe`, and the `trigger/*` methods you need.
3. Ship a `curupira-extension.toml` with `kind = "trigger"` and a console script /
   `python -m` entry.
4. Support `--curupira-print-manifest` on stdout for `plugins install pip:…`.

See `plugins/test-fixtures/python-ext/` for a minimal example.

Extensions discover and normalize tasks, validate their configuration, and receive
lifecycle events. They must not select coding agents, build agent argv, clone
repositories, or manage worktrees — the Rust host owns those steps.

## Write a JavaScript / TypeScript extension

Use the same framing and methods. Publish an npm package whose `bin` speaks the
protocol on stdio. TypeScript packages should compile to JS or run under
`tsx`/`node` as documented in the package. See
`plugins/test-fixtures/node-ext/` and `plugins/test-fixtures/ts-ext/`.

## Security

Third-party extensions run with your user privileges. Subprocesses are not a
sandbox. Do not install untrusted packages. Curupira never installs packages
during discovery; install commands ask for confirmation unless `--yes` is set.
