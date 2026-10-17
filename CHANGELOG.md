# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Fixed

- **GitHub trigger discovery is implemented again.** `curupira_github` queries GitHub Search
  through GraphQL with the token from `gh auth token` (cached for five minutes), pages through
  results lazily, and yields each match once per poll cycle. Previously both triggers returned
  no tasks.
- **GitHub pull-request items expose the documented placeholders** (`${pull_request_number}`,
  `${pull_request_head_ref}`, `${pull_request_head_sha}`, and the rest), plus `${repo}`.
- **GitHub filters are validated with Pydantic models** (`curupira-sdk[pydantic]`). Unknown
  states, sort orders, and merge states are rejected during `validate` with the field name.
- `curupira_sdk` tests no longer skip the Pydantic-model case when Pydantic is installed.

### Changed

- **Repository is a uv workspace under `packages/`:** `packages/curupira-core` (Rust crate; the
  protocol crate is now the `protocol` module of the core), `packages/curupira-python` (PyPI
  `curupira`), `packages/curupira-python-sdk` (`curupira-sdk`), and one package per official
  trigger under `packages/plugins/`. Each package owns its tests. No symlinks remain. Build all
  distributions with `uv build --all-packages --out-dir dist`.
- **Official trigger modules are renamed** from `curupira_official.<name>_ext` to
  `curupira_<name>` (`curupira_github`, `curupira_azure`, `curupira_trello`, `curupira_monday`).
  Each is published as its own `curupira-<name>` distribution, and `curupira` depends on them.
  Extension manifests installed before this change still launch `curupira_official.*`; reinstall
  them with `curupira plugins install`.
- The `curupira` wheel no longer embeds Python plugin code, and the Rust host no longer falls back
  to a `python/` directory in the working tree for `PYTHONPATH`.
- **Architectural rewrite:** the CLI host (command parsing, configuration, dispatch,
  scheduling, execution, storage, and process supervision) is implemented in **Rust** and
  distributed on PyPI via **maturin** wheels. `pip install curupira` / `uv tool install
  curupira` still provides the `curupira` and `curu` console commands.
- **Coding agents are built into the Rust core** (`crates/curupira/src/agents/`). The host
  builds native argv for OpenCode, Claude Code, Codex, Cursor, Gemini CLI, GitHub Copilot
  CLI, Kilo, pi, and Qwen Code, then runs them with `process::run_process`. The
  `curupira-agents` process extension and the `agent/buildArguments` /
  `agent/interactiveLaunch` RPCs are removed. Extensions are **task sources only**.
- **Git checkout and worktrees are owned by the Rust core** (`crates/curupira/src/vcs.rs`):
  shared base checkouts, deterministic per-task worktrees from `origin`'s default branch,
  `checkout = "main"` without fetch/switch, and `setup_script` after a fresh clone only.
- **Pluggy and in-process Python plugins are removed.** Extensions are separate processes
  speaking JSON-RPC 2.0 over length-prefixed stdin/stdout (see `protocol/PROTOCOL.md`).
  Official trigger integrations live under `plugins/` / `python/curupira_official/`.
  **cron** remains built into the Rust binary. New commands: `plugins install|uninstall|info`
  (plus existing `plugins list`).
- The supported Python import surface remains `curupira.__version__` only (plus the
  shipped `curupira_sdk` / `curupira_official` modules). Third-party packages must
  implement the process protocol for triggers instead of `curupira.triggers` /
  `curupira.agents` entry points.
- **`trigger/poll` returns a single task:** `{ "task": <object|null> }` instead of
  `{ "tasks": [...] }`. The host calls poll repeatedly until `null` or
  `settings.polling.batch_size`. `null` ends the current round and is not an error.
- **Trigger type names** match Python function names with underscores:
  `github_issues`, `github_pull_requests`, `azure_cli_pull_requests`,
  `trello_cli_cards`, `monday_items` (replacing hyphenated names). Update
  `trigger_type` in existing settings TOML accordingly.
- The third-party SDK distribution is renamed from `curupira-extension` to
  `curupira-sdk` (import `curupira_sdk`).
- The interactive `tui` command currently runs continuous dispatch with status lines
  (ratatui dashboard parity is follow-up work). Official trigger `poll` implementations
  return `task: null` until forge discovery is fully reattached to the process
  protocol; configuration validation and in-core agent argv building are live.

### Added

- **`curupira-sdk`** (`curupira_sdk`): declarative Python SDK for process extensions.
  Register triggers with `@app.trigger` (no parentheses); parameter schemas and defaults
  come from the function signature; each poll returns one item or `None`. Optional
  extra: `curupira-sdk[pydantic]` for Pydantic v2 models. Official extensions use the SDK;
  the CLI wheel ships `curupira_sdk` alongside `curupira_official`.
- Global `[settings].log_level` (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`; default
  `INFO`) and the process-wide CLI flag `--log-level` control console, file, and TUI
  verbosity. More internal debug logs cover feed construction, discovery batches,
  admission, checkout, and subprocess starts. Uncaught crashes persist detailed reports
  under `~/.curupira/logs/crashes/` (version, platform, traceback, command context) and
  enable `faulthandler` dumps in `~/.curupira/logs/faulthandler.log`, independent of the
  configured log level.
- GitHub dispatch revalidates current issue and pull-request state before admitting a
  candidate (once per admission; not again immediately before agent start). Closed or
  merged items leave the queue, issues with an open closing or Development-linked pull
  request do not invoke the coding-agent CLI (stale issue sessions are retired), and
  recovered PR sessions restart when the head SHA, draft flag, title, or body changes.
  Completed snapshots retain an explicit next action so unchanged work is not repeated
  every dispatch cycle; a failed completion-verification call clears completed state so
  the next cycle retries instead of skipping forever. Transient revalidation errors defer
  a candidate without dropping its saved session or stopping the scheduler. Closing-PR
  lookup uses GraphQL ``closedByPullRequestsReferences`` and fails closed when the result
  set spans more than one page.

### Changed

- Finite `run --size` drains count only tasks that are actually admitted after
  revalidation, including recovered sessions; discarded candidates do not consume the
  limit.
- Recovered GitHub tasks are revalidated at admission; discovery filters such as
  `-linked:pr` alone do not protect saved sessions. Pull-request sessions recovered from
  a pre-upgrade database without a head SHA restart once when the refreshed snapshot
  supplies one.
- One-shot and initial polls gather every automation feed together: a ``DispatchError``
  from one feed is logged and skipped while other feeds still contribute;
  ``dispatch_next_task`` tries the next candidate when revalidation discards one.
- Docs distinguish configuration-time discovery filters from scheduler-side revalidation
  and completed-state retention.

### Documentation

- New automations reference page: trigger overview, a minimal TOML example per trigger,
  first-run commands, a security note and common errors. English only; Spanish and
  Portuguese will follow.
- TUI assistant docs: clearer description of the in-panel agent, session start and
  saved-agent behavior.
- GitHub docs clarify token prerequisites and scopes, `repo` vs `repository`, the
  `project:` Search qualifier (no board-column filtering), and that issue/PR title and
  body placeholders are untrusted prompt input. Contributor-facing GitHub provider paths
  and configuration model names moved from `docs/en/github.md` into `CONTRIBUTING.md`.
- Coding-agent CLI profile models (`CliProfileBase` and every registered provider
  profile) document each field with `Field(description=...)` derived from the adapter
  argument mapping, so schema-driven CLI docs can read descriptions without duplicating
  class-docstring `Attributes:` blocks.
- Automation (trigger) configuration models expose English `Field(description=...)`
  text on every field, including shared base fields, so `model_json_schema()` can drive
  CLI documentation without duplicating `Attributes:` blocks in class docstrings.
- `ExecutionSettings`, `PollingSettings`, and `RepositoryConfiguration` expose
  `Field(description=...)` on every field (and keep a short class docstring naming the
  TOML table) so generated CLI/config help can read descriptions from the Pydantic
  schema without duplicating an `Attributes:` block.
- `ApplicationSettings`, `AgentsSettings`, and `AgentDefaults` expose non-empty
  `Field(description=...)` text on every field (and model docstrings without
  duplicated `Attributes:` blocks) so CLI help can read configuration docs from the
  Pydantic schema.
- Added a GitHub task source guide (`docs/en/github.md`) covering issue and pull-request
  triggers, prerequisites and token scopes, configuration field defaults, selection and
  deduplication, prompt placeholders, worktrees, and common errors. The README GitHub
  sections now summarize and link to that page.
- Removed the README "Trello listener" section, which described a `trello-cli` trigger
  that Curupira does not ship; the README now points to trigger plugins instead.
- Each coding-agent provider has its own page under "Providers and agents". The provider
  table and the coding-agent CLIs in the installation requirements are generated from the
  agent registry, so a new provider only adds its page and one nav line. The README
  provider section now links to the documentation instead of repeating CLI arguments.
- The provider overview lists Kilo's `auto_approve` permission override.
- Added the GitHub Copilot CLI provider guide, including its headless permissions and
  authentication environment-variable precedence.

### Changed

- Since GraphQL Search (#163), Curupira no longer filters board items by Status (Todo);
  `project:` is only a Search qualifier, and `state` is an explicit filter that defaults
  to `open`.
- **Breaking:** configuration splits into `[repositories.<alias>]`, `[agents.*]`, and
  `[automations.*]` (replacing nested `coding_agents.automations`). Each repository alias
  requires a full Git `remote` URL and may set `path` / `setup_script`. Automations
  reference the alias with `repository = "<alias>"`. Forge identity (`repo`) stays on
  GitHub/Azure triggers only and is independent of the clone URL, so an Azure remote can
  pair with public GitHub issues.
- **Breaking:** GitHub discovery uses GraphQL Search over `httpx` with a token from
  `gh auth token`. Trigger types are `github-issues` and `github-pull-requests` (replacing
  `issue` / `github-cli-pull-requests`). Typed TOML filters (`labels`, `exclude_labels`,
  `assignee`, `linked_pull_request`, `draft`, `mergeable`, `ci_status`, …) replace free-form
  `query` / `jq`. Clone/worktree management uses native `git clone <remote>` instead of
  `gh repo clone`.
- Built-in providers (coding agents and triggers) live under `src/curupira/providers/<name>/`
  and register through Pluggy hooks loaded by `curupira.manager`. A provider may contribute
  coding-agent adapters (`curupira_coding_agent_adapters`), triggers (`curupira_triggers`),
  or both — for example the GitHub provider contributes issue and pull-request triggers.
  The shared `CodingAgentCliAdapter` contract stays under `curupira.agents`; task contracts
  stay under `curupira.tasks`. Compatibility re-exports keep `curupira.agents.<name>` and
  `curupira.tasks.<name>` import paths working. Third-party plugins still use the
  `curupira.agents` / `curupira.triggers` entry-point groups and `curupira.plugins`.
  Provider tests live under `tests/providers/<name>/`.
- Trigger plugin API v2: discovery is a general async source that returns a typed Pydantic
  `Task.item` (`Trigger.item_model`). Prompt placeholders are the item model's fields,
  flattened by `flatten_for_template` (scalars as strings, `None` as empty, booleans as
  `true`/`false`, nested values as compact JSON). `prompt_fields` / `prompt_context`
  default from the item model. `FeedDependencies` no longer injects `gh`/`az`; built-in
  triggers construct clients from `runner`. Existing automation TOML placeholders stay
  valid. In-flight `RunningCodingSession` snapshots from API v1 cannot be resumed after
  upgrade — restart `watch`. Coding-agent adapters remain CLI-based.
- Task deadlines use `settings.task_timeout_minutes` (default 20) instead of optional
  `task_timeout_seconds`. Omit the key to keep the 20-minute default; the value is
  converted to seconds when starting the coding agent or setup script.
- CLI dispatch is unified under `run`: a finite drain (formerly `batch`, with optional
  `--size`) is the default, and continuous polling is `run --watch` (formerly `watch`).
  The standalone `batch` and `watch` commands are removed. `run --dry-run` still previews
  one task without reserving or executing. `tui` is unchanged.
- Install instructions in the README and documentation use `uv tool install curupira`
  without a version pin, with a note on pinning `curupira==X.Y.Z` when needed.

### Added

- Built-in monday.com board item discovery (`trigger_type = "monday-items"`) through the
  GraphQL API over `httpx` (`API-Version: 2026-10`), with optional `group_ids` filtering,
  string-preserved item IDs, cursor pagination that continues across polls (expired
  cursors reset to the first page; later-page failures return partial results),
  `Retry-After` / `retry_in_seconds` for transient rate limits, permanent handling for
  single-query complexity overflows, per-feed deduplication, and actionable auth/GraphQL
  errors that never echo the API token. Docs: `docs/en/monday.md`.
- Embedded coding-agent assistant in `curu tui`: `Ctrl+G` opens a half-width side panel,
  `F6` toggles focus with the main dashboard, and the chosen agent is saved in
  `[assistant]` in your settings TOML. Missing executables and config write failures show
  a clear message instead of a stack trace. Docs: `docs/en/assistant.md`.
- Pure-data `InteractiveLaunchSpec` and optional
  `CodingAgentCliAdapter.interactive_launch` for verified interactive coding-agent CLI
  invocations (Claude Code, Codex, OpenCode, Cursor, Gemini CLI, GitHub Copilot CLI,
  Kilo CLI, pi, and Qwen Code). Helpers `default_pty_env` (allowlisted PTY environment;
  does not forward provider API keys) and `spec_available` support a later embedded
  terminal panel; no process or PTY is started here. The default returns `None`
  (unverified), so `PLUGIN_API_VERSION` is unchanged and existing plugins keep working.
  Callers must resolve `model` first; `ensure_interactive_model_resolved` rejects the
  literal `auto` when the adapter has no `auto_model`. Gemini CLI and GitHub Copilot CLI
  declare `auto_model = "auto"` from their official docs alongside Cursor. Interactive
  Cursor emits `--mode` only for documented `plan`/`ask` (not `agent`); pi prompt
  separators assume pi >= 1.x.
- Reusable `PtyTerminal` Textual widget (`curupira.tui.pty_terminal`) for an embedded
  interactive PTY, intended as the building block for a future side-panel coding
  assistant. It spawns a child with `pty.fork`, emulates the stream with `pyte`
  (LGPL-3.0, dynamic dependency), forwards keys/paste (DECCKM, xterm modified keys,
  bracketed paste when the child enables mode 2004), resizes via `content_size` +
  `TIOCSWINSZ`/`SIGWINCH`, keeps the last screen with an exit status overlay on the
  last content row (covering that row if the child exited without a trailing newline),
  clears scrollback on emulator `reset`/`resize`, and cleans up in `on_unmount` (plus
  an `atexit` safety net). Public API: `PtyTerminal(argv, env, cwd,
  escape_key="ctrl+g")` with `write()`, `restart()`, and a `Finished` message. Linux
  and macOS only in v1; Windows mounts an unsupported placeholder. Not wired into the
  orchestrator layout or configuration yet. Reader feeds pyte in 256-byte slices under
  a 5 ms budget; render path caches styles, coalesces runs, refreshes dirty strip rows
  at ~30 fps, and keeps scrollback without `HistoryScreen`. Throughput script:
  `scripts/measure_pty_throughput.py --runs 3`. Observed ranges (Textual `run_test`
  `(120, 40)`, 20 s, 1 ms ticker, Linux 6.12.94+, Python 3.11.17) vary by host: on
  4 CPUs, `yes | head -c 50M` 0.345-0.371 MB/s (p99 16.2-17.2 ms), `seq 2000000`
  0.522-0.561 MB/s (p99 19.6-21.7 ms), `cat` 40 MiB 0.814-0.850 MB/s (p99 54.4-62.3 ms);
  on 8 CPUs, yes 0.258-0.277 MB/s (p99 18.6-20.0 ms), seq 0.346-0.374 MB/s (p99
  26.3-28.3 ms), cat 0.505-0.619 MB/s (p99 76.1-82.6 ms). Across both machines the
  envelope is yes 0.258-0.371 MB/s (p99 16.2-20.0 ms), seq 0.346-0.561 MB/s (p99
  19.6-28.3 ms), cat 0.505-0.850 MB/s (p99 54.4-82.6 ms). Loop **max** is a noisy
  tail (observed up to hundreds of ms) and is not a latency goal; the goal is p99
  only (`yes`/`seq` < 50 ms, dense `cat` < 100 ms). Outbound writes retry after
  `EAGAIN` via `add_writer`.
- Optional `[assistant]` configuration (`AssistantSettings`) for the interactive
  configuration assistant: `agent` (registered coding-agent provider) and `model`.
  Adapters may declare `auto_model` when their CLI documents native automatic model
  selection (Cursor, Gemini CLI, and GitHub Copilot CLI set `auto_model = "auto"`);
  `resolve_assistant_model` maps an unset or literal `auto` request onto that
  capability, and `validate` rejects `assistant.model = "auto"` for providers without
  it.
- Packaging guard (`scripts/check_packaged_readme.py`) that builds the sdist and
  wheel, fails when the packaged README or metadata long description contains
  `opscli` (case-insensitive; retired OpsCli branding must not ship on PyPI), and
  runs `twine check`. CI's build/smoke job and the local one-command check use it.
- Hot-reload for `run --watch` and `tui`: when the configuration file changes, new
  admissions pause until in-flight tasks finish, then settings and feeds reload from
  disk so subsequent work uses the latest configuration without interrupting running
  tasks. Invalid reloads keep admission paused until a valid TOML is saved.
- `pluggy` as a core dependency for the built-in provider contract (coding agents and
  triggers).
- Built-in Trello card discovery through Scale-Flow's JSON-first `trello-cli`, with board/list selection, string-preserved card IDs, and per-feed deduplication.
- Kilo CLI (`kilo`) as a built-in coding-agent provider, with OpenCode-compatible JSONL
  session detection and text rendering plus native model, agent, reasoning-variant, and
  permission options.
- Built-in Qwen Code support through `provider = "qwen"`, including native model,
  approval-mode, and session-turn limit options. Stream-JSON session IDs are persisted and
  resumed, and the final `result` text is rendered as task output.
- Built-in pi coding-agent support through `provider = "pi"`, including native model,
  thinking, tool allowlist/exclusion, and project-trust options. JSON-mode session IDs are
  persisted and resumed, and task output contains only assistant text blocks.
- Coding-agent plugins: installed distributions register new coding-agent adapters under
  the `curupira.agents` entry-point group, using the public `curupira.plugins` API. Each
  adapter declares its own `profile_model`, `display_name`, and `install_url`, so plugin
  profile options are validated by `curu validate` and select the adapter with
  `provider = "<name>"`. OpenCode, Codex, Claude Code, Cursor, Gemini CLI, GitHub Copilot
  CLI, Kilo CLI, pi, and Qwen Code stay built in and register through the same registry
  (`curupira.agents.registry`).
- `curu plugins list` appends one `agent:<provider>` line per coding-agent provider with
  its distribution and executable; trigger lines are unchanged.
- Coding-agent adapters can declare how they obtain session IDs and final answers without
  reimplementing process handling: override `session_id_from_line` to parse a different
  session record, set `assigns_session_id = True` to have Curupira generate a UUID that is
  persisted before the process starts and passed as `CodingTaskRequest.new_session_id`,
  or override `render_output` for a different final-answer shape. Built-in adapters keep
  their arguments and output unchanged.
- Gemini CLI is available as a coding-agent provider with native model, approval, trust,
  and resume options, plus assistant text rendered from its `stream-json` output.
- GitHub Copilot CLI (`copilot`) as a built-in provider, with profile options for model,
  custom agent, reasoning effort, and explicit tool permissions. Curupira assigns its
  session UUID, disables user questions, and preserves the CLI's raw JSONL output.

## [0.2.0] - 2026-10-08

### Added

- Pre-commit hooks via [`prek`](https://prek.j178.dev/): local Ruff and Pyrefly hooks run
  through `uv run --no-sync`, so lint and type-check use the same locked project
  environment as the commands in `AGENTS.md`. Install with `uv run --no-sync prek install`.
- Trigger plugins: installed distributions register new automation sources under the
  `curupira.triggers` entry-point group, using the public `curupira.plugins` API. Each
  trigger declares its own Pydantic `configuration_model`, so plugin options and prompt
  placeholders are validated by `curu validate`. Triggers can also provide lifecycle
  hooks (`validate_task`, `on_task_started`, `on_task_finished`) and their own
  version-control clone mechanism.
- `curu plugins list` shows every registered trigger type, its distribution, and its
  prompt placeholders.
- `Task.attributes` carries source-specific string values that are persisted with the
  task and available to trigger prompt context.

- Interactive orchestrator dashboard via `curu tui` (Textual): system metrics,
  running agents with elapsed timers, and live orchestrator logs.
- Azure DevOps pull-request discovery through the Azure CLI under the explicit
  trigger `azure-cli-pull-requests` (`az repos pr list`). Configure
  `repo` as `organization/project/repository`, with optional `status`,
  `source_branch`, and `target_branch` filters.
- `AGENTS.md` operating manual for coding agents (commands, repository map, code style,
  testing, security, and boundaries); `CONTRIBUTING.md` now links to it instead of
  duplicating those sections, and `CLAUDE.md` imports it.

### Changed

- Replace the `pre-commit` Python package with `prek` for Git hook management.
- Automation configuration is validated by the model of the registered trigger instead
  of a fixed union; existing TOML files keep working, including automations without
  `trigger_type`. The generated JSON schema now describes the shared
  `AutomationConfigurationBase` contract.
- The cron lifecycle (start timestamp and occurrence completion) moved from the executor
  into the cron trigger's hooks.

### Removed

- The Rust `crates/curupira-core` / `curupira._native` PyO3 extension, maturin
  build hook, and compiler toolchain requirement for wheels. Process supervision
  now uses only Python `asyncio` subprocess APIs.

### Fixed

- Release and TestPyPI workflows install the published wheel and run
  `curupira --config curupira.example.toml validate` before uploading.

### Changed

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
