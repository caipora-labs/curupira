# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Interactive orchestrator dashboard via `curu tui` (Textual): system metrics,
  running agents with elapsed timers, and live orchestrator logs.
- Azure DevOps pull-request discovery through the Azure CLI under the explicit
  trigger `azure-cli-pull-requests` (`az repos pr list`). Configure
  `repo` as `organization/project/repository`, with optional `status`,
  `source_branch`, and `target_branch` filters.
- `AGENTS.md` operating manual for coding agents (commands, repository map, code style,
  testing, security, and boundaries); `CONTRIBUTING.md` now links to it instead of
  duplicating those sections, and `CLAUDE.md` imports it.

### Removed

- Trigger aliases (`registry.register_alias`) and `Trigger.prompt_fields()`. No alias was
  registered; each configuration model now declares its own `prompt_fields`.

- The Rust `crates/curupira-core` / `curupira._native` PyO3 extension, maturin
  build hook, and compiler toolchain requirement for wheels. Process supervision
  now uses only Python `asyncio` subprocess APIs.

### Fixed

- Release and TestPyPI workflows install the published wheel and run
  `curupira --config curupira.example.toml validate` before uploading.

### Changed

- `trigger_type` is now a required `Literal` discriminator: automations are validated
  against exactly one configuration model, and a missing or unknown value is rejected
  with Pydantic's tagged-union error. Existing trigger names are unchanged.
- Validation rules live once in `curupira.models.base` as reusable `Annotated` types
  (`GitHubRepository`, `AzureRepository`, `TimezoneName`, `RelativeScriptPath`,
  `BoundedLimit`, `OutputLimit`). Profile flags, request limits, and
  `CommandRequest.capture_output` are strict: strings such as `"true"` or `"3"` are
  rejected instead of coerced.
- External `gh`, `az`, and coding-agent event payloads share an immutable
  `BoundaryModel`; `GhIssue.labels` is a tuple.

- CLI parsing now uses Typer instead of argparse. Command names and flags are
  unchanged (`validate`, `run`, `watch`, `batch`, plus `tui`).
- Packaging is a pure-Python `py3-none-any` wheel plus sdist. CI and publish
  workflows build and smoke-test distributions on `ubuntu-latest` only.
- Pull-request automations use only the explicit trigger
  `github-cli-pull-requests`. The short `pull_request` alias is no longer accepted,
  and discovered task identities use the same explicit type.
- Use Curupira as the sole product name across documentation and branding. Remove
  the legacy source-checkout module shim that reused the previous package name.
- Remove the leftover empty `src/gh_dispatch` package tree; task contracts live
  under `curupira.tasks`.
- CI runs the test suite on `ubuntu-latest` across Python 3.11–3.14 and smoke-tests
  the wheel on the same runner.

## [0.1.0] - 2026-10-07

### Added

- Rust crate `crates/curupira-core`, compiled with maturin into the `curupira._native`
  extension shipped in the wheel. `rust_core_version()` returns the crate version.
- Keyed automations with a `trigger_type` discriminator (`issue`,
  `github-cli-pull-requests`, `cron`) sharing one discovery, scheduling, and
  execution pipeline.
- Native provider adapters for OpenCode, Codex, Claude Code, and Cursor with
  optional `model`/`effort`/`agent` translation and explicit permission options.
- Bounded async process runner with disconnected stdin, output limits, timeouts,
  and process-group cleanup.
- Non-destructive SQLite state: incompatible files raise instead of being deleted.
- `validate`, `run` (with `--dry-run`), and `watch` commands with documented exit
  codes.
- Local dispatch for GitHub issues, pull requests, and cron tasks, with isolated
  task worktrees and persistent SQLite scheduling state.
- User and contributor guides at <https://caipora-labs.github.io/curupira/>.

### Changed

- Development tags `vX.Y.Z.devN` publish that PEP 440 version to PyPI through
  `publish.yml` (environment `pypi`) and do not open a GitHub Release. Stable
  `vX.Y.Z` tags publish to PyPI and open a GitHub Release.
- Renamed the installable package, primary console script, Python import, and product
  name from `curupi` to Curupira/`curupira`, and added the short CLI alias `curu`.
  Configuration and state now default to `~/.curupira` (example file
  `curupira.example.toml`, log `logs/curupira.log`). Task worktree branches use the
  `curupira/` prefix. The native crate is `crates/curupira-core`, imported as
  `curupira._native`.
- Renamed the installable package, console script, and Python import to `curupi`.
  Configuration and state defaulted to `~/.curupi` (example file
  `curupi.example.toml`, log `logs/curupi.log`). Task worktree branches used the
  `curupi/` prefix. The native crate was `crates/curupi-core`, imported as
  `curupi._native`.
- Configuration moved to `settings` plus `coding_agents` with global polling and
  per-automation prompts; the map key is the automation ID.
- Custom-agent names are only accepted where a verified native flag exists
  (`--agent` for OpenCode and Claude Code).
