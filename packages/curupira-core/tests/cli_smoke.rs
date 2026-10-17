use assert_cmd::cargo::cargo_bin_cmd;
use predicates::prelude::*;
use std::path::PathBuf;

fn core_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn packages_root() -> PathBuf {
    core_root().join("..")
}

/// `PYTHONPATH` entries for the official Python packages, so extensions import from the checkout.
fn python_path() -> std::ffi::OsString {
    let mut dirs = vec![packages_root().join("curupira-python-sdk/src")];
    for name in ["github", "azure", "trello", "monday"] {
        dirs.push(packages_root().join(format!("plugins/curupira-{name}/src")));
    }
    std::env::join_paths(dirs).expect("valid PYTHONPATH entries")
}

#[test]
fn version_prints_program_and_semver() {
    cargo_bin_cmd!("curupira")
        .arg("--version")
        .assert()
        .success()
        .stdout(predicate::str::starts_with("curupira 0.2.0"));
}

#[test]
fn curu_version_uses_alias_name() {
    cargo_bin_cmd!("curu")
        .arg("--version")
        .assert()
        .success()
        .stdout(predicate::str::starts_with("curu 0.2.0"));
}

#[test]
fn validate_example_config() {
    cargo_bin_cmd!("curupira")
        .current_dir(core_root())
        .env("CURUPIRA_EXTENSIONS_PATH", packages_root().join("plugins"))
        .env("CURUPIRA_PYTHONPATH", python_path())
        .args(["--config", "curupira.example.toml", "validate"])
        .assert()
        .success()
        .stdout(predicate::str::contains("Configuration is valid"));
}

#[test]
fn plugins_list_includes_builtin_cron_without_spawning_network() {
    cargo_bin_cmd!("curupira")
        .current_dir(core_root())
        .env("CURUPIRA_EXTENSIONS_PATH", packages_root().join("plugins"))
        .arg("plugins")
        .arg("list")
        .assert()
        .success()
        .stdout(predicate::str::contains("cron\tcurupira"))
        .stdout(predicate::str::contains("agent:opencode\tcurupira"))
        .stdout(predicate::str::contains("(built-in)"))
        .stdout(predicate::str::contains("github_issues"));
}

#[test]
fn run_dry_run_and_watch_are_mutually_exclusive() {
    cargo_bin_cmd!("curupira")
        .args(["run", "--dry-run", "--watch"])
        .assert()
        .failure()
        .code(2);
}
