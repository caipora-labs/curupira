//! Exit-code-oriented errors for the CLI.

use thiserror::Error;

/// Errors that map to documented CLI exit codes.
#[derive(Debug, Error)]
pub enum CurupiraError {
    #[error("Configuration error: {0}")]
    Config(String),
    #[error("Dispatch error: {0}")]
    Dispatch(String),
    #[error("Plugin error: {0}")]
    Plugin(String),
    #[error("Runtime setup error: {0}")]
    Runtime(String),
    #[error("{0}")]
    Message(String),
}

impl CurupiraError {
    /// Map to the public CLI exit code.
    #[must_use]
    pub fn exit_code(&self) -> i32 {
        match self {
            Self::Config(_) => 2,
            Self::Dispatch(_) | Self::Plugin(_) | Self::Runtime(_) | Self::Message(_) => 1,
        }
    }
}
