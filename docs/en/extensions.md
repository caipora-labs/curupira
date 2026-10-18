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
(plus a thin `curupira.__version__` shim). Official triggers ship as one optional
package (`curupira-plugins`, which depends on `curupira-sdk`): install with extras or
`curupira plugins install`. Built-in **cron** needs no extension package. Node.js is
required only when you install a Node-based third-party trigger extension.

```bash
# official triggers (pulls curupira-sdk transitively)
pip install 'curupira[extensions]'
# forge-named extras install the same package
pip install 'curupira[github]'
# or manage a package with the CLI (uses uvx)
curupira plugins install --yes pip:curupira-plugins
```

## Manage extensions

```bash
curupira plugins list
curupira plugins info curupira-plugins
curupira plugins install --yes path:./packages/curupira-python-plugins
curupira plugins install --yes pip:some-extension==1.2.3
curupira plugins install --yes npm:@acme/curupira-ext@1.2.3
curupira plugins uninstall some-extension
```

Discovery reads `curupira-extension.toml` manifests from
`~/.curupira/extensions/`, `CURUPIRA_EXTENSIONS_PATH`, and bundled `packages/curupira-python-plugins/`.
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

Bundled as one PyPI package `curupira-plugins`
(`packages/curupira-python-plugins/`, import `curupira_plugins`). It is **not** required
to install the CLI. PyPI extras `github` / `azure` / `trello` / `monday` / `extensions`
all install that same distribution. Register it in settings under a TOML alias with an
independent launcher (`uvx` or `npx`) and args; automations then use
`<alias>/<local-trigger>`:

```toml
[plugins.plugins-py]
type = "uvx"
args = ["--from", "curupira-plugins", "curupira-plugins"]
tools = ["*"]
```

The package ships a `curupira-plugins` console script, so `uvx` runs it directly (no
`python -m`). Use `tools` to keep only matching local triggers (`github-*`) or to drop
matches (`!monday-*`).

| Local trigger (in the package) | Example automation `trigger_type` |
| --- | --- |
| `github-issues` | `plugins-py/github-issues` |
| `github-pull-requests` | `plugins-py/github-pull-requests` |
| `azure-cli-pull-requests` | `plugins-py/azure-cli-pull-requests` |
| `trello-cli-cards` | `plugins-py/trello-cli-cards` |
| `monday-items` | `plugins-py/monday-items` |

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


@app.trigger
async def github_issues(
    repo: str,
    labels: list[str] | None = None,
    state: str = "open",
) -> Issue | None:
    """Return the next issue, or None when nothing was found."""
    # Select exactly one object (never a list). None means nothing was found.
    return None


def main() -> None:
    app.run()


if __name__ == "__main__":
    main()
```

Rules:

- Use `@app.trigger` with no parentheses to derive the **local** trigger name from
  `function.__name__` in kebab-case (`github_issues` → `github-issues`).
- Use `@app.trigger(alias="issues")` to override the local name.
- Register the launcher under `[plugins.<alias>]` in settings (`type` + `args`).
  Automations address the trigger as `<alias>/<local-name>` (for example
  `plugins-py/github-issues`).
- Function parameters are the source of truth for TOML extras. Required /
  optional / defaults / `None` come from the signature and type hints.
- Return **one** object or `None`. `None` means nothing was found and becomes
  JSON `null`. Lists, tuples, sets, and iterators are rejected, including a
  hand-built list of pairs. An empty mapping becomes an empty pair list, which
  is an item with no data, not "nothing found".
- Sync `def` and `async def` share the same decorator. The host does not pass
  `preview` or `limit` into the function.
- Mappings, dataclasses, and TypedDicts work out of the box. Pydantic v2 models
  need `curupira-sdk[pydantic]`. The SDK converts that object to a list of
  `{ "key", "value" }` string pairs. It does not add `id`, `title`, `url`, or
  any other field.
- The Rust host owns polling, concurrency, Git, worktrees, and coding agents.
  The SDK never schedules or retries dispatcher work.

### Matching TOML

Register the launcher under `[plugins.<alias>]`, then keep core automation fields on the
table with trigger arguments as siblings:

```toml
[plugins.plugins-py]
type = "uvx"
args = ["--from", "curupira-plugins", "curupira-plugins"]
tools = ["github-*"]

[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"
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
The names in the prompt are whatever fields the trigger returns. This example
uses `number`, `title`, and `url` only because `Issue` declares those fields.

### How a return value becomes pairs

The SDK converts the object before it reaches the host. Top-level keys stay in
declaration or insertion order. Each value becomes a string:

| Python value | Pair `value` |
| --- | --- |
| `str` | the same string, without extra quotes |
| `bool` | `true` or `false` |
| `int` | decimal text (`1` and `1.0` stay distinct) |
| `float` | the same text `json.dumps` would emit |
| `None` | `null` (this is a field value, not "nothing found") |
| nested mapping, list, tuple, dataclass, or model | compact JSON (`sort_keys=True`, no extra spaces) |

Rejected with `SerializationError` (surfaced as a JSON-RPC error, not as `null`):

- a top-level list, tuple, set, generator, or other collection
- a top-level string, number, or boolean
- a key that is not a string (keys are not coerced with `str`)
- an empty key, or a key containing `}` or `${`
- a duplicate key
- a non-finite float, `bytes`, `set`, `datetime`, or any other value that cannot be serialized

`describe` may still list `prompt_fields` taken from the declared return type.
That list is a hint. It is not part of the result and it does not make any key
required.

### How the host polls and interpolates

1. The host picks an enabled automation and validates configuration via
   `trigger/validate` (defaults applied from the signature).
2. It calls `trigger/poll` repeatedly, up to `settings.polling.batch_size`.
   Polling arguments are not passed to the trigger function.
3. Each call returns `{ "values": [ {"key", "value"}, ... ] }`,
   `{ "values": [] }`, or `{ "values": null }`.
4. `null` ends the current round. An empty list is still a result. Errors use
   JSON-RPC error codes and are not the same as `null`.

The CLI substitutes `${key}` with the pair's string value in one pass. Text
that a value inserts is not scanned again, so a value of `${other}` stays
literal. A placeholder with no matching key is left unchanged. `${repository}`
(the forge identity derived from the Git remote) and `${automation}` (the
automation name) are supplied by the host. A result key with either of those
names is an error. Keys that are not ordinary identifiers are still written as
`${issue-number}`, `${foo.bar}`, `${123}`, or `${a b}`.

The host does not know which keys a plugin uses. Two identical lists are the
same task; the identity is a hash of the list in the order the extension sent
it, stored with completion and resume state. Completed tasks from protocol v1
do not match these keys.

### Manifest

Ship a `curupira-extension.toml` and support `--curupira-print-manifest` on
stdout for `plugins install pip:…`. See `packages/curupira-core/tests/fixtures/python-ext/`
for a minimal protocol fixture, and
`packages/curupira-python-plugins/src/curupira_plugins/__main__.py` for a full SDK example.

Extensions discover and normalize tasks, validate their configuration, and receive
lifecycle events. They must not select coding agents, build agent argv, clone
repositories, or manage worktrees — the Rust host owns those steps.

## Write a JavaScript / TypeScript extension

Use the same framing and methods. Publish an npm package whose `bin` speaks the
protocol on stdio. TypeScript packages should compile to JS or run under
`tsx`/`node` as documented in the package. See
`packages/curupira-core/tests/fixtures/node-ext/` and
`packages/curupira-core/tests/fixtures/ts-ext/`.

Poll results must use `{ "values": null }`, `{ "values": [] }`, or
`{ "values": [{ "key": "...", "value": "..." }] }`. Do not return a task object
or an array of items.

## Security

Third-party extensions run with your user privileges. Subprocesses are not a
sandbox. Do not install untrusted packages. Curupira never installs packages
during discovery; install commands ask for confirmation unless `--yes` is set.
