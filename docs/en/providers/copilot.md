# GitHub Copilot CLI

Curupira runs [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli)
non-interactively with JSON output and a session id it assigns:

```text
copilot --output-format=json --no-ask-user --session-id=<id> [options] --prompt=<prompt>
```

## Install and sign in { #install }

```sh
npm install -g @github/copilot   # or: brew install copilot-cli / winget install GitHub.Copilot
copilot login
```

See the [official installation guide](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)
for prerequisites.

Instead of `copilot login` you can provide a token. Copilot reads `COPILOT_GITHUB_TOKEN`,
then `GH_TOKEN`, then `GITHUB_TOKEN`; classic `ghp_` tokens are not supported. If `GH_TOKEN`
is already exported for the GitHub CLI, Copilot picks it up first, so make sure that token
has Copilot access. Curupira never reads or forwards credentials.

## Profile options { #options }

| Option | Native argument | Notes |
| --- | --- | --- |
| `model` | `--model=<model>` | `auto` lets Copilot choose. |
| `agent` | `--agent=<agent>` | A configured custom agent. |
| `effort` | `--reasoning-effort=<level>` | `low`, `medium`, `high`, `xhigh`, or `max`. |
| `allow_all_tools = true` | `--allow-all-tools` | Permits every tool. |
| `allow_tools` | `--allow-tool=<a,b>` | Permits selected tools and patterns, such as `shell(git:*)` and `write`. |
| `deny_tools` | `--deny-tool=<a,b>` | Denies tools; deny rules win over allow rules. |

Curupira always adds `--no-ask-user`, because an unattended run cannot stop to ask a
question, and passes the prompt as `--prompt=<prompt>` so a leading dash stays text.

### Headless tool permissions { #configuration-reference }

Headless runs need explicit tool permissions. Set `allow_all_tools = true`, or list what is
allowed in `allow_tools` and what is forbidden in `deny_tools`. Each list is passed as one
comma-separated argument, so an entry cannot contain a comma. Curupira never adds broader
flags such as `--allow-all`, `--yolo`, or path and URL bypasses.

## Example { #example }

```toml
[agents.profiles.copilot]
provider = "copilot"
model = "auto"
effort = "high"
allow_tools = ["shell(git:*)", "write"]
deny_tools = ["shell(rm:*)"]
```

## Sessions { #sessions }

Curupira creates a UUID before the first run and passes it with `--session-id`. The same
flag resumes an interrupted task; no separate `--resume` flag is used.
