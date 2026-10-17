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
binary, the declarative SDK (`curupira_sdk`), and the official extension modules
shipped in the wheel.

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
| `curupira-github` | `github_issues`, `github_pull_requests` |
| `curupira-azure` | `azure_cli_pull_requests` |
| `curupira-trello` | `trello_cli_cards` |
| `curupira-monday` | `monday_items` |
| `curupira-agents` | `opencode`, `claude`, `codex`, `cursor`, `gemini`, `copilot`, `kilo`, `pi`, `qwen` |

**cron** remains inside the Rust CLI (not an extension).

## Write a Python extension with curupira-sdk

Install the SDK (stdlib-only by default; Pydantic is optional):

```bash
pip install curupira-sdk
# optional structured models:
pip install 'curupira-sdk[pydantic]'
```

The wheel that ships the CLI already includes `curupira_sdk` for official
extensions. Third-party packages should depend on `curupira-sdk` explicitly.

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
stdout for `plugins install pip:…`. See `plugins/test-fixtures/python-ext/` for
a minimal protocol fixture, and `python/curupira_official/github_ext.py` for a
full SDK example.

## Write a JavaScript / TypeScript extension

Use the same framing and methods. Publish an npm package whose `bin` speaks the
protocol on stdio. TypeScript packages should compile to JS or run under
`tsx`/`node` as documented in the package. See
`plugins/test-fixtures/node-ext/` and `plugins/test-fixtures/ts-ext/`.

Poll results must use `{ "task": null }` or a single task object — never a task
array.

## Security

Third-party extensions run with your user privileges. Subprocesses are not a
sandbox. Do not install untrusted packages. Curupira never installs packages
during discovery; install commands ask for confirmation unless `--yes` is set.
