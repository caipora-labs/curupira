//! Curupira CLI — Rust host for automations and process-based extensions.

pub mod agents;
pub mod cli;
pub mod config;
pub mod cron;
pub mod dispatch;
pub mod error;
pub mod extensions;
pub mod process;
pub mod prompt;
pub mod protocol;
pub mod runtime;
pub mod storage;
pub mod vcs;
pub mod version;

use std::ffi::OsString;

/// Run the CLI with the given argv (including program name) and return a process exit code.
#[must_use]
pub fn run<I, T>(args: I) -> i32
where
    I: IntoIterator<Item = T>,
    T: Into<OsString> + Clone,
{
    match cli::execute(args) {
        Ok(code) => code,
        Err(error) => {
            eprintln!("{error}");
            1
        }
    }
}
