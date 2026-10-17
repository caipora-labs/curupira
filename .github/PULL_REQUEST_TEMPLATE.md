## Summary

## Behavior and tests

- [ ] Behavioral tests cover the change (no authenticated agents or network access)
- [ ] `cargo test --manifest-path packages/curupira-core/Cargo.toml` passes
- [ ] `uv run --no-sync pytest` passes
- [ ] `uv run --no-sync ruff check .` and `uv run --no-sync ruff format --check .` pass
- [ ] `cargo clippy --manifest-path packages/curupira-core/Cargo.toml -- -D warnings` and `cargo fmt --manifest-path packages/curupira-core/Cargo.toml --all -- --check` pass
- [ ] `uv build --all-packages --out-dir dist` passes

## Documentation

- [ ] README/CONTRIBUTING/AGENTS/CHANGELOG updated if user-facing behavior changed
- [ ] `packages/curupira-core/curupira.example.toml` still validates if configuration changed
