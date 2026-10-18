# Installation

Curupira is a Rust command-line program. Install that same program with npm or from
PyPI. Both commands are `curupira` and `curu`, and both use `~/.curupira/` for
`settings.toml`, the SQLite state file, workspaces, and worktrees. Moving from pip to npm keeps that directory; the npm package does not
create a second configuration path.

The source repository is [caipora-labs/curupira](https://github.com/caipora-labs/curupira).

## Requirements

{{ requirements_list() }}

Published binaries cover:

- Linux x64 and ARM64 with glibc
- Linux x64 and ARM64 with musl (Alpine)
- macOS x64 (Intel) and ARM64 (Apple Silicon)
- Windows x64 and ARM64

32-bit systems and other operating systems are not published. Installation does not
compile Rust and does not need a Rust toolchain. The npm command is a small Node.js
wrapper that executes the prebuilt binary directly: it does not change the working
directory, environment, or configuration, and it exits with the Rust process status.
A process listing shows Node.js as the parent of that process. The Rust process is
the one that holds `~/.curupira/dispatch.lock`.

`import curupira` and `curupira.__version__` exist only in the PyPI install. Plugins
are started by the launcher you set in `settings.toml` (`uvx` or `npx`), with either
install. Curupira does not install Python or a private Node.js environment for them. If
`uvx` or `npx` is missing, validation reports that the launcher was not found on `PATH`.

## Install with Node.js

```bash
npm install -g curupira
```

Run it once without a global install:

```bash
npx curupira --help
```

npm installs the optional package that matches this operating system, CPU, and C
library (`@caipora-labs/curupira-linux-x64`, and the other platform packages listed in the
[package README](https://github.com/caipora-labs/curupira/blob/main/packages/curupira-npm/README.md)).
Connectors are not included: you register them under `[plugins.<alias>]` in your
settings, see [Plugins and connectors](plugins.md).

## Install with Python

[`uv`](https://docs.astral.sh/uv/) installs the platform wheel from PyPI. The wheel
contains the Rust CLI. Python is used for packaging and for optional `uvx` extensions,
not to interpret the CLI.

```bash
uv tool install curupira
# or
pip install curupira
```

Built-in cron works out of the box. Connectors such as GitHub are registered in your
settings, see [Plugins and connectors](plugins.md).

To pin a specific version, use `uv tool install "curupira==X.Y.Z"`.

## Check the install

`curupira --version` and `curu --version` print the installed version. Validate a
configuration without calling agent CLIs:

```bash
curupira --config curupira.example.toml validate
```

## Create a configuration

Curupira reads `~/.curupira/settings.toml` by default. Download the example configuration:

```bash
mkdir -p ~/.curupira
curl -fsSL https://raw.githubusercontent.com/caipora-labs/curupira/main/packages/curupira-core/curupira.example.toml \
  -o ~/.curupira/settings.toml
```

On Windows PowerShell:

```powershell
New-Item -ItemType Directory -Force "$HOME\.curupira"
Invoke-WebRequest `
  -Uri https://raw.githubusercontent.com/caipora-labs/curupira/main/packages/curupira-core/curupira.example.toml `
  -OutFile "$HOME\.curupira\settings.toml"
```

Edit repositories, queries, and prompts in the TOML. The `~/.curupira` directory also stores state and workspaces. Pass `--config path/to/settings.toml` to use another file.
