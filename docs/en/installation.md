# Installation

## Requirements

{{ requirements_list() }}

- [`uv`](https://docs.astral.sh/uv/) to install the application.

## Install

The package is not yet published to PyPI. Install it from GitHub:

```bash
uv tool install git+https://github.com/caipora-labs/curupi.git
```

Confirm the command is available with `curupi --version`.

## Create a configuration

OpsCli reads `~/.curupi/settings.toml` by default. Download the example configuration:

```bash
mkdir -p ~/.curupi
curl -fsSL https://raw.githubusercontent.com/caipora-labs/curupi/main/curupi.example.toml \
  -o ~/.curupi/settings.toml
```

On Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$HOME\.curupi"
Invoke-WebRequest `
  -Uri https://raw.githubusercontent.com/caipora-labs/curupi/main/curupi.example.toml `
  -OutFile "$HOME\.curupi\settings.toml"
```

Edit repositories, queries, and prompts in the TOML. The `~/.curupi` directory also stores state and logs. Pass `--config path/to/settings.toml` to use another file.
