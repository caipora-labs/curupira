# `@caipora/curupira`

npm distribution of the [Curupira](https://github.com/caipora-labs/curupira) command-line
interface. The package installs the same Rust executable published on PyPI and exposes
the `curupira` and `curu` commands. It does not reimplement the CLI and it does not
compile Rust on install.

## Install

Node.js 20 or newer:

```bash
npm install -g @caipora/curupira
```

```bash
npx @caipora/curupira --help
```

Python, pip, uv, and Rust are not required to install or run the CLI.

The PyPI package installs the same program:

```bash
pip install curupira
```

Both installs read `~/.curupira/settings.toml`, store state in `~/.curupira/`, and use the
dispatch lock `~/.curupira/dispatch.lock`. An existing PyPI configuration keeps working
after you switch to npm.

## Platforms

npm publishes a prebuilt binary for:

| Package | System |
| --- | --- |
| `@caipora/curupira-linux-x64` | Linux x64, glibc |
| `@caipora/curupira-linux-arm64` | Linux ARM64, glibc |
| `@caipora/curupira-linux-x64-musl` | Linux x64, musl (Alpine) |
| `@caipora/curupira-linux-arm64-musl` | Linux ARM64, musl (Alpine) |
| `@caipora/curupira-darwin-x64` | macOS Intel |
| `@caipora/curupira-darwin-arm64` | macOS Apple Silicon |
| `@caipora/curupira-win32-x64` | Windows x64 |
| `@caipora/curupira-win32-arm64` | Windows ARM64 |

The main package depends on these as optional dependencies. npm installs the one that
matches the current operating system, CPU, and C library. Other systems and 32-bit
architectures are not published. The command fails with the supported list when the
platform package is missing.

## Extensions

This package does not install a Python or Node.js environment for plugins. Extensions
keep the launchers configured in `settings.toml`:

- `type = "uvx"` runs `uvx` (Python on `PATH`)
- `type = "npx"` runs `npx` (Node.js on `PATH`)

Built-in cron and the coding-agent adapters are inside the Rust binary. If `uvx` or
`npx` is missing, validation reports that the launcher was not found on `PATH`.

PyPI extras such as `curupira[extensions]` are not part of this npm package. Install
official triggers with `curupira plugins install` or by configuring a launcher. The
Python module `curupira.__version__` is only provided by the PyPI install.

## Wrapper

`curupira` and `curu` are Node.js entry points that execute the native binary directly
(no shell). They pass arguments, stdin, stdout, and stderr through unchanged, keep the
working directory and environment, and exit with the Rust process status. `curu` is the
same executable with a different process name, so `curu --version` prints `curu`.

A process listing shows Node.js as the parent of the Rust process. The Rust process is
the one that takes the dispatch lock.
