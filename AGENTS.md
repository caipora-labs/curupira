# AGENTS.md

Instructions for coding agents. Humans start at [CONTRIBUTING.md](CONTRIBUTING.md).
A task or prompt overrides this file.

## Project

Curupira (Caipora Labs) runs local automations for developers. The **CLI host is Rust**
(`crates/curupira`), distributed on PyPI via **maturin** (`pip install curupira`).
Python ships the binary plus official **trigger** extension modules under
`python/curupira_official/`. Console scripts: `curupira` and `curu`.

Automations are configured in TOML (`~/.curupira/settings.toml`). `validate` checks
configuration; `run` / `run --watch` / `tui` dispatch work. One process holds
`~/.curupira/dispatch.lock`.

**cron** and all **coding-agent adapters** are built into the Rust binary. Task-source
triggers (GitHub, Azure DevOps, Trello, monday.com, and third-party sources) are
**process extensions** (JSON-RPC 2.0, length-prefixed stdin/stdout). See
[protocol/PROTOCOL.md](protocol/PROTOCOL.md) and [docs/en/extensions.md](docs/en/extensions.md).

## Architecture

- **Rust host:** clap CLI, TOML config, SQLite state, Git clone/worktree/setup,
  process runner, built-in coding-agent argv builders, extension registry/host for
  triggers, cron trigger, dispatch loop.
- **Extensions:** separate OS processes that discover tasks only. Discovery reads
  `curupira-extension.toml` only (never executes code to list). Launch via argv
  (executable / `uvx` / `npx`), never a shell string.
- **Coding agents:** modules under `crates/curupira/src/agents/`. The host builds
  native argv and runs the CLI with `process::run_process`. No extension RPC.
- **Python package:** thin `curupira.__version__` + `curupira_official.*` trigger
  modules. No Pluggy. No in-process plugin import API.

```
CLI (Rust) --JSON-RPC/stdio--> trigger extension (Python / Node / …)
     |
     +--> built-in cron
     +--> git checkout / worktree / setup_script
     +--> built-in coding-agent adapters --> agent CLI process
```

## Repository map

| Path | Look here when |
| --- | --- |
| `crates/curupira/` | Rust CLI and host logic |
| `crates/curupira/src/agents/` | Built-in coding-agent adapters |
| `crates/curupira/src/vcs.rs` | Clone, worktree, setup_script |
| `crates/curupira-protocol/` | Framing, manifests, JSON-RPC types |
| `python/curupira/` | Version export / `python -m curupira` shim |
| `python/curupira_official/` | Official trigger extension servers |
| `plugins/` | Official + test-fixture manifests |
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
- Match each coding agent's documented native flags; omit unset optional flags.

## Never

- Start headless subprocesses with a shell string.
- Use FFI bridges to Python/Node; extensions are processes.
- Reintroduce Pluggy or in-process `curupira.triggers` / `curupira.agents` entry points.
- Route coding agents through the extension protocol.
- Delegate Git clone/worktree/setup to extensions.
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
