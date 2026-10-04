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
changes to `gh-dispatch.example.toml` must keep `test_example_configuration_is_valid` green.

## Architecture boundaries

- `models/` — validated Pydantic contracts only; no I/O.
- `clients/` — one native CLI adapter per provider plus the `gh` boundary and the
  async process runner. Adapters translate typed profiles into literal argument
  vectors; they never pass commands through a shell.
- `feeds.py` — task discovery (`GitHubTaskFeed`, `CronTaskFeed`, multiplexing).
- `executor.py` / `scheduler.py` / `dispatcher.py` — shared execution pipeline used
  identically by every trigger type.
- `repositories/` — SQLite persistence with validated payloads; incompatible files
  raise instead of being deleted.
- `cli.py` — argument parsing and exit codes only.

To add a feed, implement the `TaskFeed` protocol (`poll` + `stream`) and wire it in
`dispatcher.create_task_feeds`. To add a provider, subclass `CodingAgentCliAdapter`,
add a profile model in `models/profiles.py`, and register the provider in
`create_cli_adapter`. Custom-agent selection must use a verified native flag; when none
exists, reject configured `agent` values during validation instead of reinterpreting
them. Cover new behavior with fakes in `tests/` — never start authenticated agents or
hit the network in tests.

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
`src/gh_dispatch/_version.py`; the build backend reads it, and the CLI reports it.

To cut a release:

1. Move the `Unreleased` entries in `CHANGELOG.md` into a new version section.
2. Bump `__version__` in `src/gh_dispatch/_version.py` to match.
3. Run the full verification suite and confirm `uv build` plus
   `uv run --no-sync twine check dist/*` pass.
4. Before the first production publication, run the `testpypi.yml` workflow manually
   from `main` to rehearse the upload to TestPyPI and verify the installed package.
5. Tag the validated commit as `vX.Y.Z` and push the tag. The `publish.yml` workflow
   publishes that version to PyPI; the `release.yml` workflow attaches the distributions
   to the matching GitHub release.

PyPI publishing uses Trusted Publishing (OIDC), so no API tokens are stored. Before
publishing, a PyPI maintainer registers this repository as a trusted publisher for the
`gh-dispatch` project with owner `mariotaddeucci`, repository `gh-dispatch`, workflow
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
