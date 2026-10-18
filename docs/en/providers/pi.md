# pi

Curupira runs [pi](https://www.npmjs.com/package/@earendil-works/pi-coding-agent) in JSON
mode:

```text
pi --mode json [options] -- <prompt>
```

## Install and sign in { #install }

pi needs Node.js 22.19.0 or newer.

```sh
npm install -g @earendil-works/pi-coding-agent
```

Sign in with pi's `/login` command, or export the API-key variable of your model
provider. Curupira never reads or stores credentials.

## Profile options { #options }

| Option | Native argument | Notes |
| --- | --- | --- |
| `model` | `--model <model>` | An exact or fuzzy pattern; may include `provider/id`. |
| `model_provider` | `--provider <provider>` | Requires `model`. Named so it does not clash with Curupira's `provider`. |
| `effort` | `--thinking <level>` | `off`, `minimal`, `low`, `medium`, `high`, `xhigh`, or `max`. |
| `tools` | `--tools a,b` | Allowlist of tools pi can use. |
| `exclude_tools` | `--exclude-tools a,b` | Tools to remove. |
| `approve = true` | `--approve` | Trust the project's resources for this run. |
| `approve = false` | `--no-approve` | Do not trust them for this run. |
| `agent` | — | Not supported; rejected. |

When `approve` is left out, pi's own project-trust setting applies. pi does not ask before
each tool call, and its JSON mode cannot show the trust prompt; when that setting is
`ask`, protected project resources are skipped unless you set `approve`.

!!! note "Prompts that start with `@`"
    pi reads `@path` as a file include, so a prompt that begins with `@` may be treated
    as a file reference.

## Example { #example }

```toml
[agents.profiles.pi]
provider = "pi"
model = "anthropic/claude-sonnet-4"
model_provider = "anthropic"
effort = "high"
tools = ["read", "edit", "write"]
exclude_tools = ["bash"]
# approve = true   # trust project resources for this run
```

## Sessions { #sessions }

pi writes a session header to its JSON output; that id is saved with the task. An
interrupted task resumes with `--session <id>` in the same worktree, because pi groups
sessions by directory.
