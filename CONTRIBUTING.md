# Contributing

## Environment setup

Requirements: Python 3.11+, [`uv`](https://docs.astral.sh/uv/), `gh` for live
discovery (tests use fakes and need no authentication).

```bash
uv sync --dev
```

A fresh contributor verifies everything with the commands below. They must all pass
before opening a pull request; CI runs the same steps.

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

When collecting coverage, it must stay at or above 85% branch coverage
(`fail_under = 85` in `pyproject.toml`). The example configuration is covered by tests:
changes to `opscli.example.toml` must keep `test_example_configuration_is_valid` green.

## Architecture boundaries

OpsCli separates task discovery, repository version control, and coding-agent CLI
invocation into three layers. Each layer owns a contract in its `base.py`:

- `src/opscli/tasks/` discovers work. `tasks/base.py` defines `TaskFeed` (polling
  and streaming discovered tasks), `TaskSource` (discovering tasks for an automation),
  `Trigger` (trigger-specific prompt data and feed construction), and
  `FeedDependencies`. `tasks/feed.py` provides the reusable `PollingTaskFeed`, while
  `tasks/registry.py` registers trigger types and aliases. Current sources/triggers
  are implemented in `tasks/cron.py`, `tasks/github_issues.py`, and
  `tasks/github_pull_requests.py`.
- `src/opscli/vcs/` prepares repositories. `vcs/base.py` defines `VersionControl`;
  providers implement its `clone(repo, destination)` operation, while shared checkout,
  worktree, and setup behavior stays in the base class. `vcs/github_cli.py` implements
  cloning through the GitHub CLI.
- `src/opscli/agents/` invokes coding-agent CLIs. `agents/base.py` defines
  `CodingAgentCliAdapter`; an adapter implements `build_arguments(request)` to map a
  validated task request to that CLI's native arguments. The factory
  `create_cli_adapter` in `agents/__init__.py` constructs supported adapters:
  `opencode.py`, `codex.py`, `claude.py`, and `cursor.py`.

`src/opscli/storage/` is local SQLite persistence, not a version-control provider.
OpsCli does not manage authentication: provider CLIs and the user's environment provide
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
adapter in `src/opscli/agents/`; the English installation requirements are rendered from
that TOML file during the MkDocs build.

## Documentation translations

Edit the canonical English pages in `docs/en/` first. When English documentation changes,
open a follow-up pull request to synchronize the corresponding Portuguese (`docs/pt/`) and
Spanish (`docs/es/`) pages. Generated Pydantic reference stays canonical in English; other
languages should link to it rather than manually translating generated fields.

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
`src/opscli/_version.py`; the build backend reads it, and the CLI reports it.

To cut a release:

1. Move the `Unreleased` entries in `CHANGELOG.md` into a new version section.
2. Bump `__version__` in `src/opscli/_version.py` to match.
3. Run the full verification suite and confirm `uv build` plus
   `uv run --no-sync twine check dist/*` pass.
4. Before the first production publication, run the `testpypi.yml` workflow manually
   from `main` to rehearse the upload to TestPyPI and verify the installed package.
5. Tag the validated commit as `vX.Y.Z` and push the tag. The `publish.yml` workflow
   publishes that version to PyPI; the `release.yml` workflow attaches the distributions
   to the matching GitHub release.

PyPI publishing uses Trusted Publishing (OIDC), so no API tokens are stored. Before
publishing, a PyPI maintainer registers this repository as a trusted publisher for the
`opscli` project with owner `mariotaddeucci`, repository `opscli`, workflow
filename `publish.yml`, and environment `pypi`. The TestPyPI rehearsal uses a separate
`testpypi` environment and trusted publisher with workflow filename `testpypi.yml` and
audience `testpypi`. It uploads to `https://test.pypi.org/legacy/` and smoke-tests the
installation. The publish workflow checks that the full Linux test matrix, lint, type
check, and distribution build succeeded for the commit.

## Style

Ruff (lint + format) and strict Pyrefly govern style: typed signatures everywhere,
`@override` on overrides, docstrings on public modules/classes/methods, no blanket
suppressions. Test helpers may use `**overrides: Any`; keep other `Any` usage narrow
and justified.
