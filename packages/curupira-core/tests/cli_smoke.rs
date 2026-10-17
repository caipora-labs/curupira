use assert_cmd::cargo::cargo_bin_cmd;
use predicates::prelude::*;
use std::path::PathBuf;

fn core_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn packages_root() -> PathBuf {
    core_root().join("..")
}

fn workspace_root() -> PathBuf {
    packages_root().join("..")
}

/// `PYTHONPATH` entries for the official Python packages, so extensions import from the checkout.
fn python_path() -> std::ffi::OsString {
    let dirs = [
        packages_root().join("curupira-python-sdk/src"),
        packages_root().join("curupira-python-plugins/src"),
    ];
    std::env::join_paths(dirs).expect("valid PYTHONPATH entries")
}

#[test]
fn version_prints_program_and_semver() {
    cargo_bin_cmd!("curupira")
        .arg("--version")
        .assert()
        .success()
        .stdout(predicate::str::starts_with(format!(
            "curupira {}",
            env!("CARGO_PKG_VERSION")
        )));
}

#[test]
fn curu_version_uses_alias_name() {
    cargo_bin_cmd!("curu")
        .arg("--version")
        .assert()
        .success()
        .stdout(predicate::str::starts_with(format!(
            "curu {}",
            env!("CARGO_PKG_VERSION")
        )));
}

#[test]
fn validate_example_config() {
    // Example.toml uses `uvx --from curupira-plugins` for end users. Offline CI
    // validates the same file with a path-based --from against the checkout.
    let example = std::fs::read_to_string(core_root().join("curupira.example.toml"))
        .expect("read example.toml");
    let plugins_path = packages_root()
        .join("curupira-python-plugins")
        .canonicalize()
        .expect("plugins package path")
        .to_string_lossy()
        .into_owned();
    let rewritten = example.replace(
        "args = [\"--from\", \"curupira-plugins\", \"curupira-plugins\"]",
        &format!("args = [\"--from\", \"{plugins_path}\", \"curupira-plugins\"]"),
    );
    let dir = tempfile::tempdir().expect("tempdir");
    let config_path = dir.path().join("settings.toml");
    std::fs::write(&config_path, rewritten).expect("write temp settings");

    cargo_bin_cmd!("curupira")
        .current_dir(workspace_root())
        .env(
            "CURUPIRA_EXTENSIONS_PATH",
            packages_root().join("curupira-python-plugins"),
        )
        .env("CURUPIRA_PYTHONPATH", python_path())
        .env(
            "PATH",
            format!(
                "{}:{}",
                std::env::var("HOME")
                    .map(|h| format!("{h}/.local/bin"))
                    .unwrap_or_default(),
                std::env::var("PATH").unwrap_or_default()
            ),
        )
        .args(["--config", config_path.to_str().unwrap(), "validate"])
        .assert()
        .success()
        .stdout(predicate::str::contains("Configuration is valid"));
}

#[test]
fn plugins_list_includes_builtin_cron_without_spawning_network() {
    cargo_bin_cmd!("curupira")
        .current_dir(core_root())
        .env(
            "CURUPIRA_EXTENSIONS_PATH",
            packages_root().join("curupira-python-plugins"),
        )
        .arg("plugins")
        .arg("list")
        .assert()
        .success()
        .stdout(predicate::str::contains("cron\tcurupira"))
        .stdout(predicate::str::contains("agent:opencode\tcurupira"))
        .stdout(predicate::str::contains("(built-in)"))
        .stdout(predicate::str::contains("github-issues"));
}

#[test]
fn run_dry_run_and_watch_are_mutually_exclusive() {
    cargo_bin_cmd!("curupira")
        .args(["run", "--dry-run", "--watch"])
        .assert()
        .failure()
        .code(2);
}
