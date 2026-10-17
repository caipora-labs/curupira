# Process extensions

Curupira's CLI is a Rust binary. **Task sources** (except built-in **cron**) run as
**separate processes** that speak the
[extension protocol](https://github.com/caipora-labs/curupira/blob/main/packages/curupira-core/PROTOCOL.md)
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

`curupira` and `curu` are the same binary. The base wheel ships only that Rust CLI
(plus a thin `curupira.__version__` shim). Official **trigger** extension packages
(`curupira-github`, `curupira-azure`, `curupira-trello`, `curupira-monday`) and the
declarative SDK (`curupira-sdk`) are optional: install them with extras or
`curupira plugins install`. Built-in **cron** needs no extension package. Node.js is
required only when you install a Node-based third-party trigger extension.

```bash
# one official trigger (pulls curupira-sdk transitively)
pip install 'curupira[github]'
# or every official trigger
pip install 'curupira[extensions]'
# or manage a package with the CLI (uses uvx)
curupira plugins install --yes pip:curupira-github
```

## Manage extensions

```bash
curupira plugins list
curupira plugins info curupira-github
curupira plugins install --yes path:./packages/plugins/curupira-github
curupira plugins install --yes pip:some-extension==1.2.3
curupira plugins install --yes npm:@acme/curupira-ext@1.2.3
curupira plugins uninstall some-extension
```

Discovery reads `curupira-extension.toml` manifests from
`~/.curupira/extensions/`, `CURUPIRA_EXTENSIONS_PATH`, and bundled `packages/plugins/`.
**Listing never executes extension code.**

`plugins list` also shows built-in cron and the built-in coding-agent providers
(labeled `agent:<name>` with origin `built-in`).

### Runtime requirements

| Source | Needs on PATH |
| --- | --- |
| Official Python trigger extras / managed installs | `python3` (or `uvx` for `pip:` installs) |
| `pip:` installs | `uvx` (from [uv](https://docs.astral.sh/uv/)) |
| `npm:` installs | `npx` (Node.js) |
| Built-in cron and coding agents | the agent CLIs you configure (plus `git`) |

## Official extensions

Implemented under `packages/plugins/`, one package per extension (for example
`packages/plugins/curupira-github/src/curupira_github/`). They are **not** required to
install the CLI. Matching PyPI extras on `curupira` install the same distributions:

| Extension | Extra | Contributes |
| --- | --- | --- |
| `curupira-github` | `github` | `github_issues`, `github_pull_requests` |
| `curupira-azure` | `azure` | `azure_cli_pull_requests` |
| `curupira-trello` | `trello` | `trello_cli_cards` |
| `curupira-monday` | `monday` | `monday_items` |
| (all of the above) | `extensions` | every official trigger |

**cron** and all coding-agent adapters remain inside the Rust CLI (not extensions).

## Write a Python extension with curupira-sdk

Install the SDK separately (stdlib-only by default; Pydantic is optional). Official
trigger packages depend on it; third-party packages should declare it explicitly:

```bash
pip install curupira-sdk
# optional structured models:
pip install 'curupira-sdk[pydantic]'
```

### Minimal trigger

```python
from dataclasses import dataclass

from curupira_sdk import Curupira

app = Curupira(name="acme-issues", version="0.1.0")


@dataclass
class Issue:
    number: int
    title: str
    url: str
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(self.number)


@app.trigger
async def github_issues(
    repo: str,
    labels: list[str] | None = None,
    state: str = "open",
) -> Issue | None:
    """Return the next eligible issue, or None when the round is empty."""
    # Select exactly one next item from the external API (never a list).
    return None


def main() -> None:
    app.run()


if __name__ == "__main__":
    main()
```

Rules:

- Use `@app.trigger` with **no parentheses**. The trigger name is exactly
  `function.__name__` (underscores are kept; nothing is rewritten to hyphens).
- Function parameters are the source of truth for TOML extras. Required /
  optional / defaults / `None` come from the signature and type hints.
- Return **one** object or `None`. Lists, tuples, and iterators are rejected.
- Sync `def` and `async def` share the same decorator.
- Dataclasses and TypedDict work out of the box. Pydantic v2 models need
  `curupira-sdk[pydantic]`.
- The Rust host owns polling, concurrency, Git, worktrees, and coding agents.
  The SDK never schedules or retries dispatcher work.

### Matching TOML

Core automation fields stay on the table; trigger arguments are siblings:

```toml
[automations.resolve-ready-issues]
trigger_type = "github_issues"
repository = "api"          # checkout alias (core)
repo = "acme/api"           # function parameter
labels = ["bug"]
state = "open"
prompt = """
Resolve issue ${number}: ${title}
${url}
"""
```

`repository`, `prompt`, `profile`, and `checkout` are core fields — do not
declare them as function parameters (use `repo` or another name for forge ids).

### How the host polls

1. The host picks an enabled automation and validates configuration via
   `trigger/validate` (defaults applied from the signature).
2. It calls `trigger/poll` repeatedly, up to `settings.polling.batch_size`.
3. Each call must return `{ "task": <object> }` or `{ "task": null }`.
4. `null` ends the current round; the trigger stays enabled for the next poll
   interval. Errors use JSON-RPC error codes and are not the same as `null`.

### Manifest

Ship a `curupira-extension.toml` and support `--curupira-print-manifest` on
stdout for `plugins install pip:…`. See `packages/curupira-core/tests/fixtures/python-ext/`
for a minimal protocol fixture, and `packages/plugins/curupira-github/src/curupira_github/__main__.py`
for a full SDK example.

Extensions discover and normalize tasks, validate their configuration, and receive
lifecycle events. They must not select coding agents, build agent argv, clone
repositories, or manage worktrees — the Rust host owns those steps.

## Write a JavaScript / TypeScript extension

Use the same framing and methods. Publish an npm package whose `bin` speaks the
protocol on stdio. TypeScript packages should compile to JS or run under
`tsx`/`node` as documented in the package. See
`packages/curupira-core/tests/fixtures/node-ext/` and
`packages/curupira-core/tests/fixtures/ts-ext/`.

Poll results must use `{ "task": null }` or a single task object — never a task
array.

## Security

Third-party extensions run with your user privileges. Subprocesses are not a
sandbox. Do not install untrusted packages. Curupira never installs packages
during discovery; install commands ask for confirmation unless `--yes` is set.
