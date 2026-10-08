# Contributing

**Curupira** (by Caipora Labs) is the product name. The installable package, primary console script, and Python import are `curupira`. The short CLI alias is `curu`.

## Environment setup

Requirements: Python 3.11+, [`uv`](https://docs.astral.sh/uv/), `gh` for live
discovery (tests use fakes and need no authentication), and a stable [Rust](https://rustup.rs/)
toolchain when building the native extension or a wheel.

```bash
uv sync --dev
```

`uv sync` installs the Python package and the `curupira` and `curu` console scripts. It does not
compile Rust, so the CLI and the Python test suite run without a toolchain.

A fresh contributor verifies everything with the commands below. They must all pass
before opening a pull request; CI runs the same steps. `uv build` compiles the native
extension and therefore needs Rust on `PATH`.

## Verification commands

Install the documentation tools with `uv sync --group docs`, then preview the site with
`uv run mkdocs serve`.

```bash
uv run --no-sync pytest
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pyrefly check
uv build
uv run --no-sync twine check dist/*
```

## Native extension

The Rust crate is `crates/curupira-core`, matching the `curupira` distribution name.
Hatchling stays the PEP 517 backend, keeps the version in `src/curupira/_version.py`,
and keeps the `curupira` and `curu` script entry points. A wheel build hook runs maturin (PyO3)
and packs the compiled module as `curupira._native`.
Editable installs skip that compile.

When the extension is unavailable (including an editable install that has not run
`maturin develop`), `AsyncProcessRunner` explicitly keeps using its asyncio
implementation with the same output and cleanup semantics. Built wheels use the
native supervisor. To exercise the native runner locally, build the extension with
the command below before running the process tests.

Build the extension into the current environment:

```bash
uv sync --dev
uv run maturin develop
python -c "from curupira._native import rust_core_version; print(rust_core_version())"
```

`maturin develop` warns that the build backend is Hatchling. That warning is expected:
Hatchling still packages the Python project and the `curupira` and `curu` scripts, and maturin only
compiles the extension.

`rust_core_version()` returns the `curupira-core` crate version. `curupira.native.rust_core_version`
is a thin wrapper around that function. `tests/test_native.py` runs the same check when
the extension is already built and skips otherwise.

Build a wheel that includes the extension (this is what CI and `pip install` use):

```bash
uv build
```

When collecting coverage, it must stay at or above 85% branch coverage
(`fail_under = 85` in `pyproject.toml`). The example configuration is covered by tests:
changes to `curupira.example.toml` must keep `test_example_configuration_is_valid` green.

## Architecture boundaries

Curupira separates task discovery, repository version control, and coding-agent CLI
invocation into three layers. Each layer owns a contract in its `base.py`:

- `src/curupira/tasks/` discovers work. `tasks/base.py` defines `TaskFeed` (polling
  and streaming discovered tasks), `TaskSource` (discovering tasks for an automation),
  `Trigger` (trigger-specific prompt data and feed construction), and
  `FeedDependencies`. `tasks/feed.py` provides the reusable `PollingTaskFeed`, while
  `tasks/registry.py` registers trigger types and aliases. Current sources/triggers
  are implemented in `tasks/cron.py`, `tasks/github_issues.py`, and
  `tasks/github_pull_requests.py`.
- `src/curupira/vcs/` prepares repositories. `vcs/base.py` defines `VersionControl`;
  providers implement its `clone(repo, destination)` operation, while shared checkout,
  worktree, and setup behavior stays in the base class. `vcs/github_cli.py` implements
  cloning through the GitHub CLI.
- `src/curupira/agents/` invokes coding-agent CLIs. `agents/base.py` defines
  `CodingAgentCliAdapter`; an adapter implements `build_arguments(request)` to map a
  validated task request to that CLI's native arguments. The factory
  `create_cli_adapter` in `agents/__init__.py` constructs supported adapters:
  `opencode.py`, `codex.py`, `claude.py`, and `cursor.py`.

`src/curupira/storage/` is local SQLite persistence, not a version-control provider.
Curupira does not manage authentication: provider CLIs and the user's environment provide
their own authentication.

To add a task source, implement `TaskSource`, provide a `Trigger`, and register its
`trigger_type` in `tasks/registry.py`; use a dedicated issue/PR after the task layer's
`base.py` contract. A new version-control provider implements `VersionControl.clone`
and belongs in its own issue/PR after `vcs/base.py`. A new coding-agent adapter
implements `CodingAgentCliAdapter.build_arguments` and is wired into
`create_cli_adapter`; it belongs in its own issue/PR after `agents/base.py`. Trello,
Azure DevOps, and Monday are examples of services where a future task source could
belong; they are not currently supported providers. Configuration accepts only the
trigger types and agent profiles defined by the current registry and models.

Cover new behavior with fakes in `tests/` — never start authenticated agents or hit the
network in tests.

When adding a provider or CLI, update `docs/data/requirements.toml` and the corresponding
adapter in `src/curupira/agents/`; the English installation requirements are rendered from
that TOML file during the MkDocs build.

## Documentation translations

Edit the canonical English pages in `docs/en/` first. When English documentation changes,
open a follow-up pull request to synchronize the corresponding Portuguese (`docs/pt/`) and
Spanish (`docs/es/`) pages. Generated Pydantic reference stays canonical in English; other
languages should link to it rather than manually translating generated fields.

## Documentation brand tokens

The docs theme uses the Caipora Labs palette. These hex values are the brand tokens.
Do not add other brand colors without a new decision. The Material overrides live in
`docs/stylesheets/extra.css`.

| Token | Hex | Role |
| --- | --- | --- |
| `primary` | `#F7931F` | orange brand |
| `primary-deep` | `#EA6114` | contrast / CTAs |
| `skin` | `#8E4F26` | Caipora brown |
| `accent` | `#39873B` | leaf / success |
| `neutral-0` | `#FEFDFC` | background |
| `neutral-900` | `#1A1A1A` | text |

On the light scheme, the header uses `primary` with `neutral-900` text, and primary
buttons use `primary-deep`. Body links use `skin`, which stays readable on `neutral-0`.
The leaf `accent` is the hover color. The dark scheme swaps the neutrals and uses
`primary` for links. The optional product accent (`#014FC9` / `#011E58`) is not
applied on the docs theme.

## Dependency audits

`pip-audit` runs in CI against the synced development environment:

```bash
uv run pip-audit
```

Investigate every finding: upgrade the affected constraint in `pyproject.toml`,
re-sync the lockfile, and re-run the full verification suite. If a finding is not
exploitable in this project (for example, a dev-only tool with no network path to
untrusted input), document the reason in the pull request instead of adding a
permanent ignore.

## Releases

Versioning is `MAJOR.MINOR.PATCH`. The single version source is
`src/curupira/_version.py`; the build backend reads it, and the CLI reports it.
Built wheels and sdists use that string as-is, so the Git tag and the file match
character for character after the tag's leading `v`.

### PyPI development rehearsal

Tag `vX.Y.Z.devN` publishes package `X.Y.Z.devN` (PEP 440) to PyPI. Bump the version
in `src/curupira/_version.py`, commit that change, and tag the same commit. Tag
`v0.1.0.dev0` already exists and must not be reused. The next rehearsal is
`0.1.0.dev1` with tag `v0.1.0.dev1`.

1. Set `__version__` to the next unused `X.Y.Z.devN` and commit.
2. Wait until CI is green on that commit. The tag workflow publishes only after the
   multi-platform test matrix, lint, type check, and distribution install smoke tests
   have succeeded for the tagged SHA.
3. Tag that commit and push the tag:

```bash
git tag v0.1.0.dev1
git push origin v0.1.0.dev1
```

`publish.yml` builds Rust-enabled abi3 wheels on Linux (x86_64, aarch64), macOS
(arm64, x86_64), and Windows (amd64), plus one sdist. Each platform job installs its
wheel outside the repository and runs
`curupira --config curupira.example.toml validate` before the publish job merges the
artifacts, checks that the distribution version equals the tag without its leading
`v`, and uploads with Trusted Publishing (`id-token: write`, environment `pypi`).
Use the canonical dotted form `vX.Y.Z.devN`. PyPI keeps an uploaded file, so each
rehearsal needs a new suffix.

Tags that contain `.dev` do not open a GitHub Release (`release.yml` still skips
them). `testpypi.yml` is unchanged: the same `v*.dev*` tags, and a manual
`workflow_dispatch` from `main`, still target TestPyPI. The rehearsal that gates the
first stable publish is the real PyPI upload from `publish.yml`.

Stable `vX.Y.Z` tags keep the production path below. Issue #103 publishes `0.1.0`
from a commit whose `__version__` is `0.1.0`.

To cut a release:

1. Move the `Unreleased` entries in `CHANGELOG.md` into a new version section.
2. Bump `__version__` in `src/curupira/_version.py` to the stable `X.Y.Z` version.
3. Run the full verification suite and confirm `uv build` plus
   `uv run --no-sync twine check dist/*` pass.
4. Rehearse with a `vX.Y.Z.devN` tag on PyPI (see above) before the first production
   publication.
5. Tag the validated commit as `vX.Y.Z` and push the tag. The `publish.yml` workflow
   publishes that version to PyPI; the `release.yml` workflow attaches the distributions
   to the matching GitHub release.

PyPI publishing uses Trusted Publishing (OIDC), so no API tokens are stored. Before
publishing, a PyPI maintainer registers this repository as a trusted publisher for the
`curupira` project with GitHub owner `caipora-labs`, repository `curupira`, workflow
filename `publish.yml`, and environment `pypi`. Development tags `vX.Y.Z.devN` use
that same publisher. `testpypi.yml` remains a separate workflow with environment
`testpypi`, workflow filename `testpypi.yml`, and audience `testpypi`. It uploads to
`https://test.pypi.org/legacy/` and smoke-tests that installation. The publish
workflow checks that the multi-platform test matrix, lint, type check, and
distribution install smoke tests succeeded for the commit
(`scripts/require_ci_checks.py`).

## Style

Ruff (lint + format) and strict Pyrefly govern style: typed signatures everywhere,
`@override` on overrides, docstrings on public modules/classes/methods, no blanket
suppressions. Test helpers may use `**overrides: Any`; keep other `Any` usage narrow
and justified.
