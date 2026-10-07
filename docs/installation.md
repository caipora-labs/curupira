# Installation

## Requirements

{{ requirements_list() }}

- [`uv`](https://docs.astral.sh/uv/) to install the application.

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
