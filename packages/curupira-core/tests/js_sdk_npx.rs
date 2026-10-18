//! Integration tests for the Node.js SDK launched through `npx`.

use assert_cmd::cargo::cargo_bin_cmd;
use curupira::config::{PluginConfiguration, PluginLauncher};
use curupira::extensions::host::ExtensionHost;
use curupira::protocol::KeyValue;
use predicates::prelude::*;
use std::path::{Path, PathBuf};
use std::process::Command;

fn core_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn fixture_dir() -> PathBuf {
    core_root().join("tests/fixtures/js-sdk-ext")
}

fn sdk_dir() -> PathBuf {
    core_root().join("../curupira-js-sdk")
}

fn npx_available() -> bool {
    Command::new("npx")
        .arg("--version")
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

fn ensure_js_sdk_built() {
    let sdk = sdk_dir();
    let marker = sdk.join("dist/index.js");
    if marker.is_file() {
        return;
    }
    let status = Command::new("npm")
        .args(["install", "--ignore-scripts"])
        .current_dir(&sdk)
        .status()
        .expect("npm must be available to build the JS SDK fixture");
    assert!(status.success(), "npm install in curupira-js-sdk failed");
    let status = Command::new("npm")
        .args(["run", "build"])
        .current_dir(&sdk)
        .status()
        .expect("npm run build");
    assert!(status.success(), "npm run build in curupira-js-sdk failed");
}

fn ensure_fixture_installed() {
    ensure_js_sdk_built();
    let fixture = fixture_dir();
    let node_modules = fixture.join("node_modules/@caipora/curupira-sdk");
    if node_modules.is_dir() {
        return;
    }
    let status = Command::new("npm")
        .args(["install", "--ignore-scripts"])
        .current_dir(&fixture)
        .status()
        .expect("npm must be available to install the JS SDK fixture");
    assert!(status.success(), "npm install in js-sdk-ext fixture failed");
}

fn npx_plugin_config(fixture: &Path) -> PluginConfiguration {
    PluginConfiguration {
        launcher: PluginLauncher::Npx {
            args: vec!["--yes".into(), fixture.to_string_lossy().into_owned()],
        },
        tools: vec!["*".into()],
    }
}

#[test]
fn js_sdk_extension_via_npx_speaks_protocol() {
    if !npx_available() {
        eprintln!("skipping js_sdk_extension_via_npx_speaks_protocol: npx not on PATH");
        return;
    }
    ensure_fixture_installed();
    let fixture = fixture_dir()
        .canonicalize()
        .expect("js-sdk-ext fixture path");
    let launch = npx_plugin_config(&fixture);
    let mut host = ExtensionHost::spawn_plugin("js-sdk", &launch).expect("spawn via npx");
    let described = host.describe().expect("describe");
    let names: Vec<_> = described
        .triggers
        .iter()
        .map(|trigger| trigger.trigger_type.as_str())
        .collect();
    assert!(names.contains(&"sample-trigger"));
    assert!(names.contains(&"sync-trigger"));

    let none = host
        .poll_trigger(
            "sample-trigger",
            &serde_json::json!({
                "repository": "api",
                "prompt": "x",
                "note": "skip",
            }),
            false,
            1,
        )
        .expect("poll null");
    assert!(none.values.is_none());

    let item = host
        .poll_trigger(
            "sample-trigger",
            &serde_json::json!({
                "repository": "api",
                "prompt": "x",
                "note": "hello",
            }),
            false,
            1,
        )
        .expect("poll item");
    let values = item.values.expect("values present");
    assert_eq!(values.len(), 2);
    assert_eq!(values[0].key, "note");
    assert_eq!(values[0].value, "hello");
    assert_eq!(values[1].key, "ready");
    assert_eq!(values[1].value, "true");

    let sync = host
        .poll_trigger("sync-trigger", &serde_json::json!({}), false, 1)
        .expect("poll sync");
    assert_eq!(
        sync.values.unwrap()[0],
        KeyValue {
            key: "kind".into(),
            value: "sync".into(),
        }
    );

    host.shutdown().expect("shutdown");
}

#[test]
fn validate_reports_missing_npx_clearly() {
    let dir = tempfile::tempdir().expect("tempdir");
    let empty_bin = dir.path().join("empty-bin");
    std::fs::create_dir(&empty_bin).expect("mkdir");
    let config_path = dir.path().join("settings.toml");
    std::fs::write(
        &config_path,
        r#"
[settings]
workspace_dir = "~/.curupira/workspaces"
state_db_path = "~/.curupira/state.db"

[repositories.api]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "cursor"

[agents.profiles.cursor]
provider = "cursor"

[plugins.missing-npx]
type = "npx"
args = ["--yes", "curupira-js-sdk-ext-fixture"]

[automations.demo]
trigger_type = "missing-npx/sample-trigger"
repository = "api"
prompt = "x"
"#,
    )
    .expect("write settings");

    // Empty PATH so `npx` cannot resolve. cargo_bin_cmd uses an absolute binary path.
    cargo_bin_cmd!("curupira")
        .env("PATH", empty_bin.as_os_str())
        .args(["--config", config_path.to_str().unwrap(), "validate"])
        .assert()
        .failure()
        .stderr(
            predicate::str::contains("npx")
                .and(predicate::str::contains("Node.js"))
                .and(predicate::str::contains("not found on PATH")),
        );
}
