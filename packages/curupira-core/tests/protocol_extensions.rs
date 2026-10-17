use assert_cmd::cargo::cargo_bin_cmd;
use predicates::prelude::*;
use std::path::PathBuf;

fn fixture(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("tests/fixtures")
        .join(name)
}

#[test]
fn install_local_python_fixture_and_list() {
    let dir = tempfile::tempdir().unwrap();
    let home = dir.path().join("home");
    std::fs::create_dir_all(&home).unwrap();
    let fixture = fixture("python-ext");
    cargo_bin_cmd!("curupira")
        .env("HOME", &home)
        .args([
            "plugins",
            "install",
            "--yes",
            &format!("path:{}", fixture.display()),
        ])
        .assert()
        .success();
    cargo_bin_cmd!("curupira")
        .env("HOME", &home)
        // Avoid picking up repo bundled plugins in cwd
        .env("CURUPIRA_EXTENSIONS_PATH", "")
        .current_dir(dir.path())
        .args(["plugins", "list"])
        .assert()
        .success()
        .stdout(predicate::str::contains("python-test"));
}

#[test]
fn plugins_list_does_not_require_network() {
    let dir = tempfile::tempdir().unwrap();
    cargo_bin_cmd!("curupira")
        .env("HOME", dir.path())
        .env("CURUPIRA_EXTENSIONS_PATH", dir.path().join("empty"))
        .current_dir(dir.path())
        .args(["plugins", "list"])
        .assert()
        .success()
        .stdout(predicate::str::contains("cron\tcurupira"));
}
