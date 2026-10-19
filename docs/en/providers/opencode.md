# OpenCode

Curupira runs [OpenCode](https://opencode.ai) in `run` mode with JSON output. The process
working directory is the task worktree.

OpenCode 1.x:

```text
opencode run --format json --dir <worktree> [options] -- <prompt>
```

OpenCode 2.x headless runs use a private server (`--standalone`) so the task keeps the
worktree directory. Interactive 2.x sessions do not pass `--standalone`.

```text
opencode run --standalone --format json [options] -- <prompt>
```

## Install and sign in { #install }

OpenCode 1.x (`opencode-ai`):

```sh
npm install -g opencode-ai
opencode auth login
```

OpenCode 2.x (`@opencode/cli`):

```sh
npm install -g @opencode/cli
opencode auth login
```

OpenCode owns authentication for each model provider. Curupira never reads or stores
credentials.

With `api = "auto"` (the default), Curupira runs `opencode --version` once per resolved
binary and chooses the flag set from the first `x.y.z` it finds (`1.19.3` is 1.x,
`opencode v2.0.32` is 2.x). Set `api` when that probe cannot see a version.

## Profile options { #options }

| Option | Native argument | Notes |
| --- | --- | --- |
| `api` | | `"v1"`, `"v2"`, or `"auto"` (default). Selects the OpenCode 1.x or 2.x flag set. |
| `model` | `--model <provider/model>` | On 2.x a reasoning variant is part of the model: `provider/model#variant`. |
| `agent` | `--agent <agent>` | A custom OpenCode agent. |
| `effort` | `--variant` on 1.x; `#variant` on 2.x | 1.x headless passes `--variant`. 2.x appends `#<effort>` to `--model`. Ignored when `model` is unset. A model that already contains `#` cannot be combined with `effort`. |
| `auto_approve = true` | `--auto` | Approves permissions that are not explicitly denied. Use with care. |

| Flag | OpenCode 1.x headless | OpenCode 2.x headless | OpenCode 2.x interactive |
| --- | --- | --- | --- |
| `--dir <worktree>` | passed | omitted; the process working directory is the worktree | omitted |
| `--variant` | `effort` | omitted | omitted |
| `--model` | `model` | `model`, or `model#effort` when `effort` is set | same as 2.x headless |
| `--standalone` | omitted | always passed | omitted |
| `--session`, `--agent`, `--format json`, `--auto` | passed when configured | passed when configured | `--agent` and `--auto` when configured; no `--format` |

On 1.x, each run sets `OPENCODE_DB` to `<worktree>.opencode.db`, so parallel tasks do not
share OpenCode sessions or project entries. On 2.x, runs keep your OpenCode database: 2.x stores
provider credentials there, and a fresh database reports every model as unavailable. The private
`--standalone` server already keeps each task in its worktree. `--server` is not a profile option.

## Example { #example }

```toml
[agents.profiles.opencode]
provider = "opencode"
# api = "auto" # "v1", "v2", or "auto" (default)
model = "anthropic/claude-sonnet-4"
agent = "build"
# effort = "high" # 1.x: --variant high; 2.x: --model anthropic/claude-sonnet-4#high
```

## Sessions { #sessions }

The session id is the top-level `sessionID` on a JSON event (1.x and 2.x). It is saved
with the task. An interrupted task resumes with `--session <session_id>`.
