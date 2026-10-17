## Summary

## Behavior and tests

- [ ] Behavioral tests cover the change (no authenticated agents or network access)
- [ ] `cargo test -p curupira -p curupira-protocol` passes
- [ ] `PYTHONPATH=python uv run --no-sync pytest tests` passes
- [ ] `uv run --no-sync ruff check .` and `uv run --no-sync ruff format --check .` pass
- [ ] `cargo clippy -p curupira -p curupira-protocol -- -D warnings` and `cargo fmt --all -- --check` pass
- [ ] `uv run --no-sync maturin build --release --out dist -m crates/curupira/Cargo.toml` passes

## Documentation

- [ ] README/CONTRIBUTING/AGENTS/CHANGELOG updated if user-facing behavior changed
- [ ] `curupira.example.toml` still validates if configuration changed
