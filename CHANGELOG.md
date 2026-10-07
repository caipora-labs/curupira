# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Rust crate `crates/curupi-core`, compiled with maturin into the `curupi._native`
  extension shipped in the wheel. `rust_core_version()` returns the crate version.
- Keyed automations with a `trigger_type` discriminator (`issue`, `pull_request`,
  `cron`) sharing one discovery, scheduling, and execution pipeline.
- Native provider adapters for OpenCode, Codex, Claude Code, and Cursor with
  optional `model`/`effort`/`agent` translation and explicit permission options.
- Bounded async process runner with disconnected stdin, output limits, timeouts,
  and process-group cleanup.
- Non-destructive SQLite state: incompatible files raise instead of being deleted.
- `validate`, `run` (with `--dry-run`), and `watch` commands with documented exit
  codes.

### Changed

- Renamed the installable package, console script, and Python import from `opscli`
  to `curupi`. The product name remains OpsCli. Configuration and state now default
  to `~/.curupi` (example file `curupi.example.toml`, log `logs/curupi.log`). Task
  worktree branches use the `curupi/` prefix. The native crate is `crates/curupi-core`,
  imported as `curupi._native`.
- Renamed the product to OpsCli, the package and executable to `opscli`, and the
  per-user runtime directory to `~/.opscli`.
- Configuration moved to `settings` plus `coding_agents` with global polling and
  per-automation prompts; the map key is the automation ID.
- Custom-agent names are only accepted where a verified native flag exists
  (`--agent` for OpenCode and Claude Code).
