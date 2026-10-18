# Python SDK

`curupira-sdk` (import `curupira_sdk`) turns plain Python functions into Curupira
triggers. It is stdlib-only by default; Pydantic support is optional. The
[GitHub connector](plugins.md) is written with it.

## Install { #install }

```sh
pip install curupira-sdk
# optional structured models:
pip install 'curupira-sdk[pydantic]'
```

Declare `curupira-sdk` as a dependency of your package and expose a console script, so
`uvx` can run it directly.

## A minimal trigger { #minimal-trigger }

```python
from dataclasses import dataclass

from curupira_sdk import Curupira

app = Curupira(name="acme-issues", version="0.1.0")


@dataclass
class Issue:
    number: int
    title: str
    url: str


@app.trigger  # (1)!
async def github_issues(
    repo: str,  # (2)!
    labels: list[str] | None = None,
    state: str = "open",
) -> Issue | None:
    """Return the next issue, or None when nothing was found."""
    return None  # (3)!


def main() -> None:
    app.run()  # (4)!


if __name__ == "__main__":
    main()
```

1.  The local trigger name is the function name in kebab-case: `github-issues`. Use
    `@app.trigger(alias="issues")` to choose another name.
2.  Parameters are the automation's settings. Required, optional, and default values come
    from the signature and type hints.
3.  Return **one** object, or `None` when nothing was found.
4.  Speaks the protocol on stdin and stdout. Log to stderr, never to stdout.

## Use it from settings { #settings }

Register the package under an alias, then put the trigger's parameters next to the core
automation fields:

```toml
[plugins.acme]
type = "uvx"
args = ["--from", "acme-issues==0.1.0", "acme-issues"]

[automations.resolve-ready-issues]
trigger_type = "acme/github-issues"
repository = "api"          # core: the checkout alias
repo = "acme/api"           # trigger parameter
labels = ["bug"]
state = "open"
prompt = """
Resolve issue ${number}: ${title}
${url}
"""
```

`trigger_type`, `repository`, `prompt`, `profile`, and `checkout` are core fields. Do not
use them as parameter names; use `repo` or another name for forge ids. The prompt can use
exactly the fields your trigger returns: `number`, `title`, and `url` here, because
`Issue` declares them.

## Rules { #rules }

- Return **one** object or `None`. `None` means nothing was found. Lists, tuples, sets,
  and iterators are rejected, including a hand-built list of pairs.
- An empty mapping is an item with no fields, not "nothing found".
- Sync `def` and `async def` share the same decorator.
- The host does not pass `preview` or `limit` into the function.
- Mappings, dataclasses, and TypedDicts work out of the box. Pydantic v2 models need
  `curupira-sdk[pydantic]`.
- The SDK does not add `id`, `title`, `url`, or any other field. What you return is what
  the prompt gets.
- The host owns polling, concurrency, Git, worktrees, and coding agents. The SDK never
  schedules or retries work.

## How a return value becomes fields { #serialization }

The SDK flattens the returned object into `{ "key", "value" }` string pairs before it
reaches the host. Top-level keys keep their declaration or insertion order.

| Python value | Field value |
| --- | --- |
| `str` | the same string, without extra quotes |
| `bool` | `true` or `false` |
| `int` | decimal text (`1` and `1.0` stay distinct) |
| `float` | the same text `json.dumps` would emit |
| `None` | `null` (a field value, not "nothing found") |
| nested mapping, list, tuple, dataclass, or model | compact JSON (`sort_keys=True`, no extra spaces) |

These raise `SerializationError`, which reaches the host as a JSON-RPC error, not as
"nothing found":

- a top-level list, tuple, set, generator, or other collection
- a top-level string, number, or boolean
- a key that is not a string (keys are not coerced with `str`)
- an empty key, or a key containing `}` or `${`
- a duplicate key
- a non-finite float, `bytes`, `set`, `datetime`, or any other value that cannot be serialized

`describe` may list `prompt_fields` taken from the declared return type. That list is a
hint for editors and docs. It does not make any key required.

## Ship it { #ship }

- Add a `curupira-extension.toml` manifest and support `--curupira-print-manifest` so
  `curupira plugins list` can describe the package. See
  [Manifest](extensions-protocol.md#manifest).
- Test with `curupira validate` and `curupira run --dry-run` against a local path:
  `args = ["--from", "/path/to/your/package", "acme-issues"]`.

Examples in the repository:

- `packages/curupira-plugins-py/src/curupira_plugins/__main__.py`: the GitHub connector,
  a complete SDK example.
- `packages/curupira-cli/tests/fixtures/python-ext/`: a minimal protocol fixture without
  the SDK.
