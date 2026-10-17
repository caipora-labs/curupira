# AGENTS.md

Instructions for coding agents. Humans start at [CONTRIBUTING.md](CONTRIBUTING.md).
A task or prompt overrides this file.

## Project

Curupira (Caipora Labs) runs local automations for developers. The **CLI host is Rust**
(`crates/curupira`), distributed on PyPI via **maturin** (`pip install curupira`).
Python ships the binary plus official process-extension modules under
`python/curupira_official/`. Console scripts: `curupira` and `curu`.

Automations are configured in TOML (`~/.curupira/settings.toml`). `validate` checks
configuration; `run` / `run --watch` / `tui` dispatch work. One process holds
`~/.curupira/dispatch.lock`.

**cron** is built into the Rust binary. All other triggers and coding-agent adapters are
**process extensions** (JSON-RPC 2.0, length-prefixed stdin/stdout). See
[protocol/PROTOCOL.md](protocol/PROTOCOL.md) and [docs/en/extensions.md](docs/en/extensions.md).

## Architecture

- **Rust host:** clap CLI, TOML config, SQLite state, git checkout, process runner,
  extension registry/host, cron trigger, dispatch loop.
- **Extensions:** separate OS processes. Discovery reads `curupira-extension.toml` only
  (never executes code to list). Launch via argv (executable / `uvx` / `npx`), never a
  shell string.
- **Python package:** thin `curupira.__version__`, declarative `curupira_sdk`, and
  `curupira_official.*` extension modules. No Pluggy. No in-process plugin import API.

```
CLI (Rust) --JSON-RPC/stdio--> extension process (Python / Node / …)
     |
     +--> built-in cron
     +--> git checkout + coding-agent argv from agent extension
```

## Repository map

| Path | Look here when |
| --- | --- |
| `crates/curupira/` | Rust CLI and host logic |
| `crates/curupira-protocol/` | Framing, manifests, JSON-RPC types |
| `python/curupira/` | Version export / `python -m curupira` shim |
| `python/curupira_sdk/` | Declarative extension SDK (`curupira-sdk`) |
| `python/curupira_official/` | Official extension servers |
| `plugins/` | Official + test-fixture manifests |
| `plugins/sdk-python/` | Packaged `curupira-sdk` distribution metadata |
| `protocol/` | Wire protocol docs |
| `tests/` | Python packaging / manifest tests |
| `crates/curupira/tests/` | Rust CLI and extension tests |
| `curupira.example.toml` | Example config (`validate` must accept it) |
| `docs/en/` | Canonical docs |

## Always

- Cover behavior changes with Rust and/or Python tests as appropriate.
- Keep stdout of extensions for protocol frames only; logs on stderr.
- Update `CHANGELOG.md` (`Unreleased`) and `docs/en/` when user-visible behavior changes.
- After `pyproject.toml` dependency changes, run `uv lock`. Do not bump the package
  version or push tags unless releasing.

## Never

- Start headless subprocesses with a shell string.
- Use FFI bridges to Python/Node; extensions are processes.
- Reintroduce Pluggy or in-process `curupira.triggers` / `curupira.agents` entry points.
- Commit secrets. Tests must not hit the network or call real coding-agent CLIs.
- Edit `docs/pt/` or `docs/es/` in the feature change.

## Workflow

```bash
cargo test -p curupira -p curupira-protocol
CURUPIRA_EXTENSIONS_PATH=plugins CURUPIRA_PYTHONPATH=python \
  cargo run -p curupira --bin curupira -- --config curupira.example.toml validate
uv sync --dev
PYTHONPATH=python uv run --no-sync pytest tests
uv run --no-sync maturin build --release --out dist -m crates/curupira/Cargo.toml
uv run --no-sync python scripts/smoke_install.py --dist dist --config curupira.example.toml
```
