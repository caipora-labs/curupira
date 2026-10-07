# Installation

## Requirements

- Python 3.11 or newer (Linux, macOS, and Windows).
- [`uv`](https://docs.astral.sh/uv/) to install the application.
- [GitHub CLI (`gh`)](https://cli.github.com/) installed and authenticated (`gh auth login`).
- Only the CLIs used by configured profiles: [OpenCode](https://opencode.ai/), [Codex](https://developers.openai.com/codex/cli/), [Claude Code](https://code.claude.com/docs/en/cli-reference), or Cursor CLI (`agent`).

## Install

The package is not yet published to PyPI. Install it from GitHub:

```bash
uv tool install git+https://github.com/mariotaddeucci/opscli.git
```

Confirm the command is available with `opscli --version`.

## Create a configuration

OpsCli reads `~/.opscli/settings.toml` by default. Download the example configuration:

```bash
mkdir -p ~/.opscli
curl -fsSL https://raw.githubusercontent.com/mariotaddeucci/opscli/main/opscli.example.toml \
  -o ~/.opscli/settings.toml
```

On Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$HOME\.opscli"
Invoke-WebRequest `
  -Uri https://raw.githubusercontent.com/mariotaddeucci/opscli/main/opscli.example.toml `
  -OutFile "$HOME\.opscli\settings.toml"
```

Edit repositories, queries, and prompts in the TOML. The `~/.opscli` directory also stores state and logs. Pass `--config path/to/settings.toml` to use another file.
