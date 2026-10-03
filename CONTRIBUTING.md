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
uv run pytest --cov --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run pyrefly check
uv build
uv run twine check dist/*
```

Coverage must stay at or above 85% branch coverage (`fail_under = 85` in
`pyproject.toml`). The example configuration is covered by tests: changes to
`gh-dispatch.example.toml` must keep `test_example_configuration_is_valid` green.

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
   `uv run twine check dist/*` pass.
4. Tag the commit as `vX.Y.Z` and push the tag. Only tag pushes publish;
   ordinary pull-request runs never reach the publish step.

PyPI publishing uses Trusted Publishing (OIDC), so no API tokens are stored. Before
the first release, a PyPI maintainer registers this repository as a trusted publisher
for the `gh-dispatch` project with workflow filename `release.yml` and environment
`pypi`, and a matching `pypi` environment is created in the repository settings.

## Style

Ruff (lint + format) and strict Pyrefly govern style: typed signatures everywhere,
`@override` on overrides, docstrings on public modules/classes/methods, no blanket
suppressions. Test helpers may use `**overrides: Any`; keep other `Any` usage narrow
and justified.
