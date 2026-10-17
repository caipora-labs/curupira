//! Package version shared with the Python distribution layer.

/// Semver string embedded in the binary and reported by `--version`.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");
