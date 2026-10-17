# Process extensions

Curupira's CLI is a Rust binary. Triggers (except built-in **cron**) and coding
agents run as **separate processes** that speak the
[extension protocol](https://github.com/caipora-labs/curupira/blob/main/protocol/PROTOCOL.md)
(JSON-RPC 2.0 over length-prefixed stdin/stdout).

## Install the CLI

```bash
pip install curupira
# or
uv tool install curupira
```

`curupira` and `curu` are the same binary. Python is used only to distribute that
binary and the official extension modules shipped in the wheel.

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

### Runtime requirements

| Source | Needs on PATH |
| --- | --- |
| Official Python extensions (shipped) | `python3` |
| `pip:` installs | `uvx` (from [uv](https://docs.astral.sh/uv/)) |
| `npm:` installs | `npx` (Node.js) |
| Built-in cron | nothing extra |

## Official extensions

Bundled under `plugins/` and implemented in `python/curupira_official/`:

| Extension | Contributes |
| --- | --- |
| `curupira-github` | `github-issues`, `github-pull-requests` |
| `curupira-azure` | `azure-cli-pull-requests` |
| `curupira-trello` | `trello-cli-cards` |
| `curupira-monday` | `monday-items` |
| `curupira-agents` | `opencode`, `claude`, `codex`, `cursor`, `gemini`, `copilot`, `kilo`, `pi`, `qwen` |

**cron** remains inside the Rust CLI (not an extension).

## Write a Python extension

1. Depend on the framing rules in `protocol/PROTOCOL.md` (or the
   `curupira-extension` SDK under `plugins/sdk-python/`).
2. Implement `initialize`, `describe`, and the trigger/agent methods you need.
3. Ship a `curupira-extension.toml` and a console script / `python -m` entry.
4. Support `--curupira-print-manifest` on stdout for `plugins install pip:…`.

See `plugins/test-fixtures/python-ext/` for a minimal example.

## Write a JavaScript / TypeScript extension

Use the same framing and methods. Publish an npm package whose `bin` speaks the
protocol on stdio. TypeScript packages should compile to JS or run under
`tsx`/`node` as documented in the package. See
`plugins/test-fixtures/node-ext/` and `plugins/test-fixtures/ts-ext/`.

## Security

Third-party extensions run with your user privileges. Subprocesses are not a
sandbox. Do not install untrusted packages. Curupira never installs packages
during discovery; install commands ask for confirmation unless `--yes` is set.
