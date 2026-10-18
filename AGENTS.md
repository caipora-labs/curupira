# AGENTS.md

Instructions for coding agents. Humans start at [CONTRIBUTING.md](CONTRIBUTING.md).
A task or prompt overrides this file.

## Project

Curupira (Caipora Labs) runs local automations for developers. The repository is a **uv
workspace**: every package lives under `packages/`, and there are no symlinks. Docs and
repo-level config stay at the root.

- **`packages/curupira-cli/`** — Rust CLI host (crate `curupira`, binaries `curupira` and `curu`).
- **`packages/curupira-cli-py/`** — PyPI distribution `curupira` (maturin). CLI-only wheel (Rust
  binary + thin `curupira.__version__` shim). Official triggers are optional extras.
- **`packages/curupira-sdk-py/`** — PyPI distribution `curupira-sdk` (import `curupira_sdk`).
- **`packages/curupira-plugins-py/`** — PyPI distribution `curupira-plugins` (import
  `curupira_plugins`). Official trigger extensions in one package; depends on `curupira-sdk`.
  Install via `curupira[extensions]` (or forge-named extras) / `curupira plugins install`.
- **`packages/curupira-sdk-js/`** — npm package `@caipora-labs/curupira-sdk` (ESM). Declarative
  `defineTriggers` API and protocol runtime for Node.js plugins launched with `npx`.
- **`packages/curupira-cli-js/`** — npm package `@caipora-labs/curupira`. Thin wrapper that runs the
  prebuilt Rust CLI (`curupira` and `curu`). One package bundles the platform binaries built
  from the same wheels as PyPI. No second config directory and no FFI.

Automations are configured in TOML (`~/.curupira/settings.toml`). Register packages under
`[plugins.<alias>]` with `type = "uvx"` or `"npx"` and `args` for that launcher (for
example `[plugins.plugins-py]`); automations address triggers as
`<alias>/<local-trigger>` (for example `plugins-py/github-issues`). `validate` checks
configuration; `run` / `run --watch` / `tui` dispatch work. One process holds
`~/.curupira/dispatch.lock`.

**cron** and all **coding-agent adapters** are built into the Rust binary. Task-source
triggers (GitHub and third-party sources) are
**process extensions** (JSON-RPC 2.0, length-prefixed stdin/stdout). See
[packages/curupira-cli/PROTOCOL.md](packages/curupira-cli/PROTOCOL.md) and
[docs/en/extensions.md](docs/en/extensions.md).

## Architecture

- **Rust host:** clap CLI, TOML config, SQLite state, Git clone/worktree/setup,
  process runner, built-in coding-agent argv builders, extension registry/host for
  triggers, cron trigger, dispatch loop, and the protocol crate (`src/protocol/`).
- **Extensions:** separate OS processes that discover tasks only. Discovery reads
  `curupira-extension.toml` only (never executes code to list). Launch via argv
  (executable / `uvx` / `npx`), never a shell string.
- **Coding agents:** modules under `packages/curupira-cli/src/agents/`. The host builds
  native argv and runs the CLI with `process::run_process`. No extension RPC.
- **Python packages:** thin `curupira.__version__`, declarative `curupira_sdk`, and
  `curupira_plugins` trigger modules. No Pluggy. No in-process plugin import API.
- **Node.js packages:** declarative `@caipora-labs/curupira-sdk` (`defineTriggers` + stdio
  runtime). Third-party npm plugins declare a `bin` and depend on the SDK; the host
  starts them with `npx` (no global install, no Curupira-managed Node env).
  `curupira` is only a distribution of the Rust CLI, not an SDK.

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
| `packages/curupira-cli/` | Rust CLI and host logic (`Cargo.toml`, `Cargo.lock`) |
| `packages/curupira-cli/src/agents/` | Built-in coding-agent adapters |
| `packages/curupira-cli/src/vcs.rs` | Clone, worktree, setup_script |
| `packages/curupira-cli/src/protocol/` | Framing, manifests, JSON-RPC types |
| `packages/curupira-cli/PROTOCOL.md` | Wire protocol spec |
| `packages/curupira-cli/tests/` | Rust CLI and extension tests; `tests/fixtures/` protocol fixtures |
| `packages/curupira-cli/curupira.example.toml` | Example config (`validate` must accept it) |
| `packages/curupira-cli-py/` | PyPI `curupira` package, maturin build, packaging tests |
| `packages/curupira-cli-py/scripts/` | Release scripts (`publish_tag.py`, `stamp_release_version.py`, `verify_dist_version.py`, `check_packaged_readme.py`) |
| `packages/curupira-sdk-py/` | Declarative extension SDK (`curupira-sdk`) |
| `packages/curupira-plugins-py/` | Official triggers (`curupira-plugins`): source, manifest, tests |
| `packages/curupira-sdk-js/` | Declarative Node.js SDK (`@caipora-labs/curupira-sdk`) |
| `packages/curupira-cli-js/` | Single npm CLI distribution with bundled platform binaries |
| `.github/scripts/` | CI gate (`require_ci_checks.py`) |
| `docs/en/` | Canonical docs |

## Versions

Each package has its own version and is released by its own git tag,
`publish/<project>/<version>` (see [CONTRIBUTING.md](CONTRIBUTING.md#releases)). The tag is the source:

- `curupira-sdk` and `curupira-plugins`: `dynamic = ["version"]`, read from
  `publish/curupira-sdk-py/<version>` and `publish/curupira-plugins-py/<version>` by hatch-vcs
  (`[tool.hatch.version]`). Do not write a version into their `pyproject.toml`.
- `curupira`: `dynamic = ["version"]`, so maturin takes it from `packages/curupira-cli/Cargo.toml`.
  `publish.yml` stamps that from the `publish/curupira-cli/<version>` tag before building
  (`packages/curupira-cli-py/scripts/stamp_release_version.py`).
  Its checked-in version is a placeholder; do not bump it by hand for a release.
- `@caipora-labs/curupira` uses that same `curupira-cli` tag. The stamp script writes the Cargo semver form
  (`0.3.0.dev0` → `0.3.0-dev0`) into `packages/curupira-cli-js/package.json`. All platform
  binaries are included in that one package and built from the maturin wheels, not from a
  second compile.
- `@caipora-labs/curupira-sdk` is independently released by
  `publish/curupira-sdk-js/<version>`; its npm manifest is stamped from that tag. It does
  not follow the CLI release version.
- `curupira-extension.toml` version fields are stamped the same way; the checked-in values are placeholders.
- `__version__` comes from `importlib.metadata`; never hard-code it.
- The only static versions are the pre-release lower bounds `curupira-sdk[pydantic]>=0.1.0.dev0` in
  `curupira-plugins` and `curupira-plugins>=0.1.0.dev0` in the `curupira` extras. Raise them when a
  minimum version changes, because pip ignores pre-releases without an explicit specifier.

## Always

- Cover behavior changes with Rust and/or Python tests as appropriate.
- Keep stdout of extensions for protocol frames only; logs on stderr.
- Update `CHANGELOG.md` (`Unreleased`) and `docs/en/` when user-visible behavior changes.
- Keep `docs/pt/` and `docs/es/` equivalent to `docs/en/` in the same change: every page, section,
  table row, and example that exists in English exists in both other languages. Translate prose and
  code comments; never translate keys, field names, commands, or output. Link targets keep the same
  explicit heading ids (`## Title { #id }`).
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

## Workflow

```bash
uv sync --all-packages --dev
uv run --no-sync cargo test --manifest-path packages/curupira-cli/Cargo.toml
uv run --no-sync ruff check packages
uv run --no-sync pytest
npm --prefix packages/curupira-sdk-js install
npm --prefix packages/curupira-sdk-js test
npm --prefix packages/curupira-cli-js test
uv run --no-sync cargo run --manifest-path packages/curupira-cli/Cargo.toml --bin curupira -- \
 --config packages/curupira-cli/curupira.example.toml validate
uv build --all-packages --out-dir dist
```

Each package keeps its own tests (`packages/*/tests/`, Rust tests in
`packages/curupira-cli/tests/`). The Node.js SDK uses `npm test` under
`packages/curupira-sdk-js/`. The npm CLI wrapper is tested with
`npm test` under `packages/curupira-cli-js/`.
