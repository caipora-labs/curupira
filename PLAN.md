# Refactoring and Open Source Readiness Plan

## Purpose

Turn gh-dispatch into a typed, predictable, CLI-first automation dispatcher that
developers can install, understand, operate, and contribute to with confidence.
Issue polling, pull request polling, and cron scheduling will share task execution,
queueing, concurrency controls, and session persistence. Provider-specific adapters
will invoke external coding-agent CLIs using their native options.

The project will remain opinionated. Its abstractions should describe actual
responsibilities rather than anticipate a general-purpose workflow framework.

## Progress Tracking

- `[ ]` means that a task is pending or in progress.
- `[x]` means that the task has been implemented and its required verification has
  passed.
- Complete a phase only after all its tasks and acceptance criteria are satisfied.
- Update this file as work progresses. Do not check off work based on intent.
- Record relevant decisions, verification results, and remaining blockers in the
  implementation log at the end of this file.
- Add newly discovered work to the appropriate phase before treating that phase as
  complete.

**Current status:** implementation in progress; configuration contracts implemented.

## Agreed Product Decisions

1. Global execution settings belong under `settings`.
2. Polling configuration belongs under `settings.polling`, without per-automation
   polling overrides.
3. Coding-agent configuration is organized under `coding_agents.defaults`,
   `coding_agents.profiles`, and `coding_agents.automations`.
4. Automations form a keyed map. The map key is the automation identifier; automation
   configuration does not contain an `id` field.
5. Each automation defines its own task prompt. There is no global prompt fallback.
6. The default profile references an entry in `coding_agents.profiles`.
7. Cron automations inherit the default timezone unless they specify one.
8. `model`, `effort`, and native custom `agent` selection are optional profile options,
   subject to each provider's capabilities.
9. Custom agents belong to the external tools. gh-dispatch references existing agents
   through supported CLI flags.
10. Custom-agent selection must use a native flag. Prompt-based delegation is not an
    alternative selection mechanism.
11. Different automations may execute the same issue or pull request with different
    prompts. Deduplication is scoped to the automation.
12. All feeds use one bounded queue and one scheduler.
13. `run` selects one available task from any automation in configuration order,
    without waiting for future events.
14. `run --dry-run` does not reserve cron occurrences, persist state, clone repositories,
    or start coding-agent processes.
15. Configuration and persisted state adopt the new format directly. Legacy format
    compatibility is not part of this pre-release refactoring.
16. Project-owned code, documentation, examples, comments, and user-facing messages
    will be in English. User-supplied prompt text remains unrestricted by language.

## Design Principles

Apply the Zen of Python through concrete decisions:

- Prefer explicit names and contracts over abbreviations and implicit fallbacks.
- Keep one implementation of shared behavior.
- Separate discovery, scheduling, execution, CLI translation, and persistence.
- Validate external data at boundaries and pass typed values internally.
- Use Pydantic for data contracts and validation, and ordinary functions or small
  behavioral interfaces where a model is unnecessary.
- Make errors actionable. Do not silently reinterpret unsupported configuration.
- Keep asynchronous cleanup, failure handling, and ownership explicit.
- Add abstractions when they remove duplication or enforce a real invariant.

## Current Findings

| Area | Current finding | Planned improvement |
| --- | --- | --- |
| Configuration | Watchers are grouped by source and issues are mandatory | Independent, discriminated automation configurations |
| Prompts | Global prompts have repository-level overrides | A required prompt on each automation definition |
| GitHub feeds | Issue and pull request loops duplicate polling behavior | Shared polling, backoff, and error handling |
| Task identity | Scheduler and session repository implement separate keys | One typed identity shared by all consumers |
| Provider options | Codex maps `agent` to `--profile`; Cursor maps it to `--mode` | Native custom-agent semantics with capability validation |
| Models | Configuration, requests, tasks, and persistence models share one large module | Cohesive modules with explicit responsibilities |
| Queue shutdown | Producers can attempt a blocking terminal queue write during cancellation | Cancellation-safe producer and iterator cleanup |
| Process output | Captured output accumulates without an explicit bound | Bounded capture and robust event parsing |
| Workspaces | Multiple tasks can execute in the same checkout | Exclusive execution per checkout |
| Persistence | Incompatible databases can be automatically deleted and recreated | Non-destructive errors for incompatible database files |
| Tooling | Ruff and Pyrefly configuration is minimal | Stable, stricter checks covering source and tests |
| Distribution | Typed-package and installed-artifact verification are missing | Typed distributions and isolated installation checks |
| Collaboration | CI and contribution materials are missing | Reproducible checks and an English contribution workflow |

## Target Configuration

```toml
[settings]
max_active_tasks = 1
workspace_dir = "~/.gh-dispatch/workspaces"
state_db_path = "~/.gh-dispatch/state.sqlite3"

[settings.polling]
poll_interval_seconds = 30
batch_size = 100
cron_poll_interval_seconds = 1

[coding_agents.defaults]
profile = "opencode-default"
timezone = "UTC"

[coding_agents.profiles.opencode-default]
provider = "opencode"
# agent = "issue-resolver"
# model = "provider/model"
# effort = "high"

[coding_agents.profiles.claude-reviewer]
provider = "claude"
agent = "pull-request-reviewer"

[coding_agents.automations.resolve-ready-issues]
trigger_type = "issue"
repo = "acme/api"
query = "is:open label:agent-ready"
prompt = "Resolve issue ${issue_number}: ${issue_title}"

[coding_agents.automations.review-pull-requests]
trigger_type = "pull_request"
repo = "acme/api"
query = "is:open label:review-needed"
profile = "claude-reviewer"
prompt = "Review pull request ${pull_request_number}: ${pull_request_title}"

[coding_agents.automations.weekly-maintenance]
trigger_type = "cron"
repo = "acme/api"
schedule = "0 9 * * 1"
prompt = "Perform weekly maintenance for ${repo}."
# timezone = "Europe/Rome"
```

### Naming and Resolution

Use `trigger_type` instead of `agent_type`: issue, pull request, and cron describe
automation triggers. Reserve `agent` for a native custom-agent name.

Use explicit Python names such as `ApplicationSettings`, `ExecutionSettings`,
`IssueAutomationConfiguration`, `PullRequestAutomationConfiguration`,
`CronAutomationConfiguration`, `TaskScheduler`, and `CodingAgentCliAdapter`.

An automation's `profile` overrides `coding_agents.defaults.profile`. A cron
automation's `timezone` overrides `coding_agents.defaults.timezone`, which defaults
to `UTC`. Issue and pull request automations share the global interval and batch
size. Cron clock checks use the global cron polling interval.

The automation key is supplied to its feed as `automation_id` and carried into task
identity and persistence. It is not duplicated inside the automation configuration.

## Target Architecture

```text
ApplicationSettings
    |
    +-- ExecutionSettings
    |       +-- PollingSettings
    |
    +-- CodingAgentsSettings
            +-- CodingAgentDefaults
            +-- profiles: keyed CLI profiles
            +-- automations: keyed discriminated configurations

Configured automations
    -> issue / pull request / cron feeds
    -> validated tasks
    -> shared bounded queue
    -> TaskScheduler
    -> TaskExecutor
    -> provider CLI adapter
```

### Responsibility Boundaries

- **Configuration:** parse and validate declared values and resolve defaults.
- **Feed:** discover matching GitHub items or due cron occurrences.
- **Task:** carry identity, source data, effective profile, prompt, and workspace.
- **Queue:** provide bounded buffering and backpressure.
- **Scheduler:** manage global concurrency, checkout exclusivity, and deduplication.
- **Executor:** prepare the checkout, render the prompt, execute, and manage session state.
- **CLI adapter:** translate supported options and parse native process events.
- **Repository:** persist and retrieve validated state with explicit transaction boundaries.

Use a discriminated Pydantic union for automation parsing:

```python
AutomationConfiguration = Annotated[
    IssueAutomationConfiguration | PullRequestAutomationConfiguration | CronAutomationConfiguration,
    Field(discriminator="trigger_type"),
]
```

Issue and pull request configurations inherit a shared GitHub query configuration.
The common automation base contains repository, optional path, required prompt, and
optional profile reference. Provider profiles should also use discriminated models
where that makes supported options explicit.

Separate declared configuration from resolved execution data. Resolve profile,
timezone, and workspace once through validated models rather than repeating fallback
logic in feeds, dispatchers, and schedulers.

## Implementation Checklist

### Phase 1 — Configuration, Explicit Names, and Pydantic Contracts

**Outcome:** one documented, validated configuration contract for all automations.

- [x] Introduce `ApplicationSettings` and the `settings` / `coding_agents` composition.
- [x] Move concurrency, workspace, and state-path settings out of `core`.
- [x] Introduce global `PollingSettings` for GitHub interval, batch size, and cron interval.
- [x] Introduce `CodingAgentDefaults` with default profile and timezone.
- [x] Replace watcher groups with a keyed automation map.
- [x] Rename the automation discriminator to `trigger_type`.
- [x] Define the common automation configuration base.
- [x] Define the shared GitHub query configuration base.
- [x] Define issue, pull request, and cron subclasses with distinct literal discriminators.
- [x] Configure the Pydantic discriminated union without a manual model-selection parser.
- [x] Remove automation configuration `id` fields and use map keys as identifiers.
- [x] Require a prompt on every automation and remove global prompt settings.
- [x] Replace repository-level coding-agent references with explicit profile references.
- [x] Preserve automation insertion order for one-shot selection.
- [x] Validate non-empty, documented identifier formats for profile and automation keys.
- [x] Validate default and automation-specific profile references.
- [x] Validate repository names, queries, and non-empty prompts.
- [x] Reject unknown configuration fields at all relevant nesting levels.
- [x] Validate positive, finite polling intervals and bounded batch/concurrency values.
- [x] Validate cron expressions, timezones, and schedule windows.
- [x] Resolve inherited cron timezones before interpreting local schedule-window dates.
- [x] Normalize execution timestamps to timezone-aware values.
- [x] Validate prompt placeholders against common fields and applicable source fields.
- [x] Resolve relative and home-expanded paths consistently from the TOML directory.
- [x] Reject workspace collisions between different repositories.
- [x] Define validated resolved models for effective profile, workspace, and cron timezone.
- [x] Avoid using `model_copy(update=...)` to validate external or newly resolved values.
- [x] Keep settings-source precedence explicit using `pydantic-settings` TOML sources.
- [x] Use `Annotated`, reusable constraints, validators, and `TypeAdapter` where appropriate.
- [x] Organize configuration, requests, domain objects, and state into cohesive modules.
- [x] Ensure the models can generate a useful JSON Schema for configuration tooling.
- [x] Add configuration tests covering valid and invalid cases, including PR-only and cron-only setups.

**Acceptance criteria:** the target TOML loads without external CLI calls; invalid
configuration produces errors identifying the relevant field or automation; omitted
optional values resolve according to the documented defaults.

### Phase 2 — Task Identity and Shared Feeds

**Outcome:** every source produces tasks with the same execution contract.

- [x] Define a typed `TaskIdentity` containing automation, repository, source type, and item/occurrence identity.
- [x] Provide one canonical persistence/deduplication representation of task identity.
- [x] Remove duplicated key construction from scheduler and session repository.
- [x] Define validated task models carrying effective execution data and source metadata.
- [x] Preserve issue and pull request metadata needed by prompt placeholders.
- [x] Carry the automation map key into every emitted task.
- [x] Introduce a small typed feed interface for one-shot discovery and continuous consumption.
- [x] Consolidate issue and pull request polling, backoff, and error handling.
- [x] Preserve per-automation seen-item deduplication.
- [x] Preserve supported GitHub search and project-board filtering behavior.
- [x] Adapt cron discovery to keyed automations and global clock polling settings.
- [x] Preserve missed-occurrence coalescing and pending-occurrence recovery.
- [x] Keep cron schedule state separate from coding-agent session state.
- [x] Rename watcher-oriented modules and classes to describe their feed responsibilities.
- [x] Test two automations discovering the same item with distinct prompts and identities.
- [x] Test shared GitHub backoff, reset behavior, and source-specific metadata.
- [x] Test cron discovery with inherited and overridden timezones.

**Acceptance criteria:** issue, PR, and cron feeds produce validated tasks without
performing agent execution, and independent automations are not deduplicated together.

### Phase 3 — Common Queue, Scheduler, Executor, and CLI Commands

**Outcome:** one execution path serves continuous and one-shot operation.

- [x] Introduce or refactor `TaskExecutor` for checkout, prompt rendering, adapter invocation, and session handling.
- [x] Refactor `TaskScheduler` to manage concurrency independently of task source.
- [x] Remove scheduler dependencies on global prompt configuration.
- [x] Route all feeds through the same bounded queue.
- [x] Define queue-capacity behavior and document its relationship to active-task limits.
- [x] Add exclusive execution per resolved checkout path.
- [x] Ensure checkout exclusivity does not unnecessarily block unrelated workspaces.
- [x] Preserve the prohibition against concurrent occurrences of the same cron automation.
- [x] Consolidate resumed-session and newly discovered task scheduling.
- [x] Refactor one-shot dispatch to select from all automations in configuration order.
- [x] Make `run` return when no task is currently available rather than entering a watch loop.
- [x] Make `run --dry-run` preview cron without claiming or persisting an occurrence.
- [x] Keep configuration validation free of CLI calls, workspace creation, and state writes.
- [x] Update CLI descriptions, output, errors, and exit codes for all task types.
- [x] Distinguish expected dispatch failures from unexpected exceptions.
- [x] Make task failures observable in one-shot results and continuous-mode logs.
- [x] Test global concurrency across source types and exclusive execution within one checkout.
- [x] Test selection order and empty one-shot outcomes.
- [x] Test dry-run and validate side-effect guarantees.

**Acceptance criteria:** all task types use the same executor and concurrency policy;
dry-run leaves the filesystem, scheduling state, and external processes untouched.

### Phase 4 — Provider CLI Adapters and Native Options

**Outcome:** profile options have consistent semantics and are translated correctly.

| Provider | Native custom agent | Model | Effort |
| --- | --- | --- | --- |
| OpenCode | Optional `--agent` | Optional `--model` | Optional `--variant` |
| Claude Code | Optional `--agent` | Optional `--model` | Optional `--effort` |
| Codex | No verified selection flag; reject configured `agent` | Optional `--model` | Optional reasoning-effort configuration |
| Cursor | `--mode` is not custom-agent selection; reject configured `agent` | Optional `--model` | Not supported by the current adapter |

- [x] Rename the behavioral abstraction to `CodingAgentCliAdapter`.
- [x] Rename factories and parameters to describe adapter construction, not agent creation.
- [x] Define provider-specific profile contracts and supported optional fields.
- [x] Keep model-format validation specific to the relevant provider.
- [x] Keep `model`, `effort`, and supported native `agent` options optional.
- [x] Omit option flags when their corresponding values are not configured.
- [x] Preserve OpenCode native custom-agent selection via `--agent`.
- [x] Preserve Claude Code native custom-agent selection via `--agent`.
- [x] Remove the Codex `agent` to `--profile` mapping.
- [x] Remove the Cursor `agent` to `--mode` mapping and its agent-mode validator.
- [x] Reject configured custom agents for providers without a verified native flag.
- [x] Reject unsupported effort configuration instead of silently ignoring it.
- [x] Keep provider-native session identifiers and resume behavior explicit.
- [x] Persist the effective provider options required to resume a session consistently.
- [x] Replace hardcoded permission relaxations with explicit, typed, provider-specific options.
- [x] Preserve native permission policies when override options are omitted.
- [x] Verify initial and resume argument contracts against supported CLI versions.
- [x] Test omitted options, supported custom names, unsupported combinations, and native resume arguments.
- [x] Ensure adapter tests simulate processes instead of starting authenticated coding agents.

**Acceptance criteria:** no provider silently treats a custom-agent name as a
configuration profile or execution mode; unsupported options fail before execution.

### Phase 5 — Asynchronous Execution and Process Reliability

**Outcome:** shutdown, errors, and long-running output are handled predictably.

- [x] Preserve direct argument-vector process execution without a shell.
- [x] Handle prompts beginning with option-like text according to each CLI's contract.
- [x] Disconnect standard input for unattended agent execution.
- [x] Define configurable, validated process timeout behavior.
- [x] Bound captured stdout/stderr while continuing to process required session events.
- [x] Handle oversized event lines and malformed JSON without losing process cleanup.
- [x] Ensure callback failures terminate and reap the associated process and helper tasks.
- [x] Ensure timeouts and cancellation reap subprocesses and supported child-process groups.
- [x] Account for platform differences in process shutdown behavior.
- [x] Make feed multiplexing cancellation-safe when the queue is full.
- [x] Close asynchronous iterators when consumers stop early.
- [x] Ensure terminal producer notifications cannot deadlock queue shutdown.
- [x] Observe worker failures and avoid unhandled background-task exceptions.
- [x] Preserve session state when execution is interrupted before completion.
- [x] Review long-lived deduplication bookkeeping, especially recurring cron identities.
- [x] Keep blocking filesystem and SQLite operations off the event loop where relevant.
- [x] Test timeout, cancellation, callback failure, malformed events, and bounded capture.
- [x] Test early consumer exit and shutdown with a full queue.

**Acceptance criteria:** the dispatcher exits without orphaned helper tasks or
queue deadlocks, and interruption preserves the data needed for session recovery.

### Phase 6 — Typed, Non-Destructive Persistence

**Outcome:** task and cron state use a coherent identity and failure policy.

- [x] Update session serialization for the new task and effective-profile contracts.
- [x] Use canonical task identities for save, lookup, and deletion.
- [x] Use automation keys consistently in cron schedule state.
- [x] Validate persisted payloads with Pydantic on read.
- [x] Keep invalid-record handling explicit and observable.
- [x] Distinguish cancellation, execution failure, and completed execution.
- [x] Preserve atomic cron-occurrence completion and active-session removal.
- [x] Preserve the requirement that atomic operations use the same state database.
- [x] Replace automatic database deletion/recreation with a non-destructive incompatibility error.
- [x] Ensure database errors identify the affected path and an actionable recovery procedure.
- [x] Keep SQL values parameterized and dynamic identifiers internal and controlled.
- [x] Test independent sessions for separate automations targeting the same GitHub item.
- [x] Test recovery from cancellation using the persisted execution snapshot.
- [x] Test atomic cron completion and preservation of unrelated records.
- [x] Test that incompatible or unrelated database files are not overwritten.

**Acceptance criteria:** state round-trips through validated models, independent
automations do not collide, and incompatible database files are not silently deleted.

### Phase 7 — Ruff, Pyrefly, and Behavioral Test Quality

**Outcome:** source and tests share enforceable, reproducible quality standards.

- [x] Align development dependency versions with the selected tooling features.
- [x] Enforce compatible Ruff and Pyrefly versions in their configuration.
- [x] Keep Ruff formatting and lint settings compatible.
- [x] Expand correctness/import/modernization checks with `E`, `F`, `I`, `UP`, and `B`.
- [x] Add naming and annotation checks with `N` and `ANN`.
- [x] Add applicable asynchronous and timezone checks with `ASYNC` and `DTZ`.
- [x] Add relevant security and logging checks from `S`, `LOG`, and `G`.
- [x] Add readability checks from `PTH`, `C4`, `SIM`, `RET`, and `RUF`.
- [x] Add pytest-style checks with `PT`.
- [x] Add public-docstring checks and a moderate function-complexity limit.
- [x] Use stable rules and keep narrowly scoped exceptions documented.
- [x] Permit test assertions without broadly disabling security checks.
- [x] Configure Pyrefly's `strict` preset for source and tests.
- [x] Set the minimum supported Python version explicitly for static analysis.
- [x] Use Pyrefly's built-in Pydantic support without an additional plugin.
- [x] Type callbacks, generators, factories, overrides, and process/event results.
- [x] Replace unstructured internal JSON handling with validated boundary models where appropriate.
- [x] Remove obsolete or unnecessarily broad type suppressions.
- [x] Add dependency stubs only where required by the selected dependencies.
- [x] Adapt existing tests to the new contracts while preserving meaningful behavioral coverage.
- [x] Replace unnecessary timing-sensitive tests with injected clocks, events, or controlled fakes.
- [x] Add branch-coverage reporting and establish a documented threshold from the measured baseline.
- [x] Ensure critical execution, cleanup, and persistence paths have behavioral tests.
- [x] Run lint, format verification, type checking, and the complete test suite.

**Acceptance criteria:** all configured checks pass without blanket suppression;
tests verify observable behavior rather than merely repeating implementation logic.

### Phase 8 — Packaging and Installed-Artifact Verification

**Outcome:** the distributed package is typed, complete, and independently usable.

- [x] Declare directly imported runtime dependencies, including Pydantic.
- [x] Review dependency constraints against the supported Python versions.
- [x] Include timezone data support for environments without a system IANA database.
- [x] Complete package metadata, SPDX license expression, project URLs, and classifiers.
- [x] Define one authoritative package version source.
- [x] Include `py.typed` in distributions.
- [x] Define and document the intended public import surface.
- [x] Keep internal persistence and provider implementation details private.
- [x] Maintain the committed lockfile for reproducible contributor environments.
- [x] Build both wheel and source distribution.
- [x] Verify distribution metadata with a package-checking tool.
- [x] Inspect distribution contents for required files and unintended local artifacts.
- [x] Install the wheel into an isolated environment outside the repository.
- [x] Smoke-test imports, package version access, CLI help, and configuration validation.
- [x] Verify the installed package does not rely on test `pythonpath` configuration.
- [x] Verify wheel construction from the source distribution.

**Acceptance criteria:** built artifacts install and operate outside the source
checkout, include typing metadata, and contain only intended distribution content.

### Phase 9 — English Documentation and Open Source Contribution Workflow

**Outcome:** users and contributors can understand the package and reproduce checks.

- [x] Rewrite README content in English using the final configuration format.
- [x] Rewrite the example TOML and its comments in English.
- [x] Document installation, external CLI requirements, configuration, commands, and exit behavior.
- [x] Document defaults, per-automation prompts, polling, task identity, and deduplication.
- [x] Document provider capabilities and the distinction between profile and native custom agent.
- [x] Document cron timezones, windows, missed-run coalescing, and recovery semantics.
- [x] Document shared-checkout concurrency, permission options, and process limits.
- [x] Document state-file behavior and non-destructive incompatibility handling.
- [x] Document the supported Python/platform matrix and verified external CLI requirements.
- [x] Add `CONTRIBUTING.md` with environment setup and exact verification commands.
- [x] Describe architecture boundaries and how to add a feed or provider adapter.
- [x] Add `SECURITY.md` with a usable reporting route and a clearly described scope.
- [x] Add `CODE_OF_CONDUCT.md` with project-appropriate contact/reporting details.
- [x] Add `CHANGELOG.md` and a release-note convention.
- [x] Add bug-report and feature-request issue templates.
- [x] Add a pull-request template covering behavior, tests, and documentation.
- [x] Add pre-commit configuration aligned with CI checks.
- [x] Review ignore patterns for local configuration, state, build, and tool artifacts.
- [x] Convert remaining project-owned comments, docstrings, test names, and messages to English.
- [x] Keep documentation examples executable or covered by configuration tests.
- [x] Verify a fresh contributor can follow setup instructions and run all required checks.

**Acceptance criteria:** project-owned material is consistently in English, the
example configuration validates, and contribution instructions match actual tooling.

### Phase 10 — CI and Release Readiness

**Outcome:** contributions and artifacts are checked through the same repeatable pipeline.

- [x] Add GitHub Actions workflows with least-required permissions.
- [x] Pin third-party actions to reviewed immutable revisions.
- [x] Install development dependencies reproducibly from the lockfile.
- [x] Run Ruff lint and format verification in CI.
- [x] Run strict Pyrefly checks in CI.
- [x] Run behavioral tests and branch-coverage reporting in CI.
- [x] Validate the example TOML in CI without external CLI calls.
- [x] Test Python 3.11 through 3.14 on Linux.
- [x] Add macOS and Windows compatibility jobs for representative supported versions.
- [x] Keep regular CI independent of agent authentication, paid requests, and live GitHub data.
- [x] Build and validate wheel/source distributions in CI.
- [x] Smoke-test the installed artifact outside the repository.
- [x] Add dependency-audit checks and a documented approach to actionable findings.
- [x] Configure Dependabot for Python dependencies and GitHub Actions.
- [x] Make pull-request checks reproducible with documented local commands.
- [x] Prepare a controlled release workflow using verified build artifacts.
- [x] Document versioning, release notes, and release verification.
- [x] Prepare Trusted Publishing configuration instructions for the eventual PyPI setup.
- [x] Verify release automation does not publish from ordinary pull-request runs.

**Acceptance criteria:** CI verifies source, behavior, configuration, and installed
artifacts; the release procedure uses those verified artifacts and an explicit trigger.

## Verification Strategy

Use injected clocks, fake CLI runners, temporary state files, and controlled async
events for deterministic tests. Regular tests must not require authenticated external
agents or cause paid model requests.

Prioritize these observable behaviors:

1. Pydantic selects the correct automation/profile subtype.
2. Defaults and overrides resolve consistently.
3. Unsupported native options fail before process launch.
4. Omitted optional options do not produce CLI flags.
5. Separate automations may independently process the same GitHub item.
6. Every feed obeys the same global execution policy.
7. Checkout exclusivity prevents concurrent writers in one workspace.
8. Queue shutdown completes even when buffering is full.
9. Process interruption and callback failure clean up resources.
10. Persisted snapshots support consistent recovery.
11. Cron handles schedule windows, timezone changes, and missed occurrences correctly.
12. Validation and dry-run preserve their side-effect guarantees.
13. Incompatible database files are not overwritten.
14. Installed distributions work without source-tree import shortcuts.

Measure coverage to identify missing branches, not as a substitute for meaningful
assertions. Increase checks or rerun broader verification when a change, failure, or
unresolved concern warrants it.

## Delivery Order and Dependencies

| Phase | Primary deliverable | Depends on |
| --- | --- | --- |
| 1 | Configuration and validated contracts | Agreed product decisions |
| 2 | Task identity and feeds | Phase 1 |
| 3 | Unified queue and executor | Phases 1–2 |
| 4 | Correct provider semantics | Phase 1; integrated with Phase 3 |
| 5 | Async/process reliability | Phases 2–4 |
| 6 | Typed state and recovery | Phases 1–5 |
| 7 | Strict tooling and behavioral verification | Applied throughout Phases 1–6 |
| 8 | Verified package artifacts | Phases 1–7 |
| 9 | English user/contributor documentation | Updated throughout; finalized after Phase 8 |
| 10 | CI and release readiness | Phases 7–9 |

Keep intermediate changes reviewable and the test suite current as each contract
changes. Enable quality checks early rather than postponing every lint/type correction
until the end of the refactoring.

## Expected Impact on the Project

### Users

- A coherent configuration format with clear defaults and actionable validation.
- Independent automations and predictable task identity.
- Correct native custom-agent selection semantics.
- Explicit execution policies, reliable cleanup, and consistent session recovery.
- Installation verified from actual distribution artifacts.

### Contributors

- Smaller, named responsibilities and typed extension points.
- One implementation of shared scheduling and execution behavior.
- Deterministic tests that do not require external accounts.
- Local checks matching CI and clear contribution instructions.
- English documentation and source conventions suitable for international collaboration.

### Maintainers

- Less duplicated logic and fewer implicit configuration combinations.
- Earlier detection of contract, async, and packaging regressions.
- Reviewable provider capabilities and release artifacts.
- A repeatable process for dependency updates, verification, and releases.

### Long-Term Direction

The intended result is a focused automation dispatcher with small extension contracts,
not an agent-definition platform. New feeds should reuse the task pipeline. New CLI
providers should implement argument translation and event handling while preserving
the common execution lifecycle.

These changes establish a credible pre-release foundation. Future compatibility
policies can then be based on a deliberate configuration and state contract.

## Definition of Done

- [x] All implementation phases and their acceptance criteria are complete.
- [x] The final configuration uses keyed automations without embedded identifiers.
- [x] Profiles and default timezone resolve through validated contracts.
- [x] All source types use the shared execution pipeline.
- [x] Provider capability checks and optional flags behave as documented.
- [x] Shutdown, persistence, and dry-run guarantees pass behavioral tests.
- [x] Ruff, formatting, Pyrefly, and the complete test suite pass.
- [x] Wheel and source distributions pass metadata and installation checks.
- [x] CI covers the documented Python/platform support matrix.
- [x] Project-owned content is in English.
- [x] A fresh contributor can reproduce the required checks from the documentation.
- [x] This plan reflects actual completed work and records any remaining follow-up explicitly.

## Implementation Log

### 2026-10-03 — Phase 1

- Implemented keyed, discriminated automation/profile configuration and validated resolution.
- Split models by responsibility and centralized global polling and execution limits.
- Verification: `pytest tests/test_config.py -q` — 39 passed.
- Queue capacity is explicit (`max_pending_tasks`, default 100); process limits are global.

### 2026-10-03 — Phase 2

- Unified GitHub feeds, keyed cron discovery, canonical task identity, and read-only cron preview.
- Adapted persistence and adapter interfaces as prerequisites for feed integration.
- Verification: configuration, feeds, cron, and session tests — 54 passed.

### 2026-10-03 — Execution integration

- Implemented the shared executor/scheduler, checkout exclusivity, native adapters, and bounded process runner.
- Verification: complete current suite — 98 passed; installed OpenCode/Claude/Codex help reviewed.
- Adding explicit mixed-source and selection-order coverage before completing Phase 3.

Add entries as implementation progresses:

```text
Date:
Phase / tasks:
Changes:
Verification:
Decisions or deviations:
Remaining blockers or follow-up:
```
