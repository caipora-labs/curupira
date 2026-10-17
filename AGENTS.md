# AGENTS.md

Instructions for coding agents. Humans start at [CONTRIBUTING.md](CONTRIBUTING.md).
A task or prompt overrides this file.

## Project

Curupira (Caipora Labs) runs local automations for developers. The repository is a **uv
workspace**: every package lives under `packages/`, and there are no symlinks. Docs and
repo-level config stay at the root.

- **`packages/curupira-core/`** — Rust CLI host (crate `curupira`, binaries `curupira` and `curu`).
- **`packages/curupira-python/`** — PyPI distribution `curupira` (maturin). CLI-only wheel (Rust
  binary + thin `curupira.__version__` shim). Official triggers are optional extras.
- **`packages/curupira-python-sdk/`** — PyPI distribution `curupira-sdk` (import `curupira_sdk`).
- **`packages/curupira-python-plugins/`** — PyPI distribution `curupira-plugins` (import
  `curupira_plugins`). Official trigger extensions in one package; depends on `curupira-sdk`.
  Install via `curupira[extensions]` (or forge-named extras) / `curupira plugins install`.

Automations are configured in TOML (`~/.curupira/settings.toml`). Register packages under
`[plugins.<alias>]` with `type = "uvx"` or `"npx"` and `args` for that launcher (for
example `[plugins.plugins-py]`); automations address triggers as
`<alias>/<local-trigger>` (for example `plugins-py/github-issues`). `validate` checks
configuration; `run` / `run --watch` / `tui` dispatch work. One process holds
`~/.curupira/dispatch.lock`.

**cron** and all **coding-agent adapters** are built into the Rust binary. Task-source
triggers (GitHub, Azure DevOps, Trello, monday.com, and third-party sources) are
**process extensions** (JSON-RPC 2.0, length-prefixed stdin/stdout). See
[packages/curupira-core/PROTOCOL.md](packages/curupira-core/PROTOCOL.md) and
[docs/en/extensions.md](docs/en/extensions.md).

## Architecture

- **Rust host:** clap CLI, TOML config, SQLite state, Git clone/worktree/setup,
  process runner, built-in coding-agent argv builders, extension registry/host for
  triggers, cron trigger, dispatch loop, and the protocol crate (`src/protocol/`).
- **Extensions:** separate OS processes that discover tasks only. Discovery reads
  `curupira-extension.toml` only (never executes code to list). Launch via argv
  (executable / `uvx` / `npx`), never a shell string.
- **Coding agents:** modules under `packages/curupira-core/src/agents/`. The host builds
  native argv and runs the CLI with `process::run_process`. No extension RPC.
- **Python packages:** thin `curupira.__version__`, declarative `curupira_sdk`, and
  `curupira_plugins` trigger modules. No Pluggy. No in-process plugin import API.

```
CLI (Rust) --JSON-RPC/stdio--> trigger extension (curupira_plugins)
     |
     +--> built-in cron
     +--> git checkout / worktree / setup_script
     +--> built-in coding-agent adapters --> agent CLI process
```

## Repository map

| Path | Look here when |
| --- | --- |
| `packages/curupira-core/` | Rust CLI and host logic (`Cargo.toml`, `Cargo.lock`) |
| `packages/curupira-core/src/agents/` | Built-in coding-agent adapters |
| `packages/curupira-core/src/vcs.rs` | Clone, worktree, setup_script |
| `packages/curupira-core/src/protocol/` | Framing, manifests, JSON-RPC types |
| `packages/curupira-core/PROTOCOL.md` | Wire protocol spec |
| `packages/curupira-core/tests/` | Rust CLI and extension tests; `tests/fixtures/` protocol fixtures |
| `packages/curupira-core/curupira.example.toml` | Example config (`validate` must accept it) |
| `packages/curupira-python/` | PyPI `curupira` package, maturin build, packaging smoke tests |
| `packages/curupira-python/scripts/` | Packaging scripts (`smoke_install.py`, `verify_dist_version.py`, `check_packaged_readme.py`) |
| `packages/curupira-python-sdk/` | Declarative extension SDK (`curupira-sdk`) |
| `packages/curupira-python-plugins/` | Official triggers (`curupira-plugins`): source, manifest, tests |
| `.github/scripts/` | CI gate (`require_ci_checks.py`) |
| `docs/en/` | Canonical docs |

## Versions

All packages share one version. Bump them together: `version` in `packages/curupira-core/Cargo.toml`
and every `pyproject.toml` under `packages/`; the `==` pins on optional `curupira-plugins`
extras in `packages/curupira-python/pyproject.toml` and on `curupira-sdk` in the plugins
`pyproject.toml`; and `__version__` in `packages/curupira-python/src/curupira/__init__.py`,
`packages/curupira-python-sdk/src/curupira_sdk/__init__.py`, and
`packages/curupira-python-plugins/src/curupira_plugins/__init__.py`.

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
uv sync --all-packages --dev
uv run --no-sync cargo test --manifest-path packages/curupira-core/Cargo.toml
uv run --no-sync ruff check packages
uv run --no-sync pytest
uv run --no-sync cargo run --manifest-path packages/curupira-core/Cargo.toml --bin curupira -- \
  --config packages/curupira-core/curupira.example.toml validate
uv build --all-packages --out-dir dist
uv run --no-sync python packages/curupira-python/scripts/smoke_install.py --dist dist \
  --config packages/curupira-core/curupira.example.toml
```

Each package keeps its own tests (`packages/*/tests/`, Rust tests in
`packages/curupira-core/tests/`).
