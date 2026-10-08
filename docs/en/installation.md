# Installation

## Requirements

{{ requirements_list() }}

- [`uv`](https://docs.astral.sh/uv/) to install the application.

## Install

Install the published package from PyPI. The source repository is
[caipora-labs/curupira](https://github.com/caipora-labs/curupira).
The package is pure Python (`py3-none-any`), so installation needs no compiler
toolchain on any supported platform.

```bash
uv tool install "curupira==0.2.0"
```

Confirm the command is available with `curupira --version`. The short alias `curu --version` runs the same program. Validate a configuration without calling agent CLIs:

```bash
curupira --config curupira.example.toml validate
```

## Create a configuration

Curupira reads `~/.curupira/settings.toml` by default. Download the example configuration:

```bash
mkdir -p ~/.curupira
curl -fsSL https://raw.githubusercontent.com/caipora-labs/curupira/main/curupira.example.toml \
  -o ~/.curupira/settings.toml
```

On Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$HOME\.curupira"
Invoke-WebRequest `
  -Uri https://raw.githubusercontent.com/caipora-labs/curupira/main/curupira.example.toml `
  -OutFile "$HOME\.curupira\settings.toml"
```

Edit repositories, queries, and prompts in the TOML. The `~/.curupira` directory also stores state and logs. Pass `--config path/to/settings.toml` to use another file.
