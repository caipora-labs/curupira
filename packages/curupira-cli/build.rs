//! Sets `CURUPIRA_VERSION`, the version the binary reports (`--version`, the TUI).
//!
//! In a git checkout it comes from the latest `publish/curupira-cli/<version>` tag, so local
//! builds show the release they are based on instead of the placeholder in Cargo.toml. Builds
//! without git or tags (source distributions, the release jobs) use Cargo.toml, which the release
//! workflow stamps from the tag.

use std::path::{Path, PathBuf};
use std::process::Command;

include!("src/version_describe.rs");

fn git(dir: &Path, args: &[&str]) -> Option<String> {
    let output = Command::new("git")
        .args(args)
        .current_dir(dir)
        .output()
        .ok()?;
    if !output.status.success() {
        return None;
    }
    Some(String::from_utf8(output.stdout).ok()?.trim().to_owned())
}

fn main() {
    let dir = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").expect("set by cargo"));
    let version = git(
        &dir,
        &[
            "describe",
            "--tags",
            "--long",
            "--match",
            "publish/curupira-cli/*",
        ],
    )
    .and_then(|describe| version_from_describe(&describe))
    .unwrap_or_else(|| std::env::var("CARGO_PKG_VERSION").expect("set by cargo"));
    println!("cargo:rustc-env=CURUPIRA_VERSION={version}");

    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed=src/version_describe.rs");
    // A new commit or tag changes the version. Only existing paths are watched: Cargo reruns the
    // script on every build for a path that does not exist.
    let mut watched = Vec::new();
    if let Some(git_dir) = git(&dir, &["rev-parse", "--absolute-git-dir"]) {
        let git_dir = PathBuf::from(git_dir);
        watched.push(git_dir.join("HEAD"));
        let common = git(&dir, &["rev-parse", "--git-common-dir"])
            .map(|common| dir.join(common))
            .unwrap_or_else(|| git_dir.clone());
        watched.push(common.join("packed-refs"));
        watched.push(common.join("refs").join("tags"));
        if let Some(branch) = std::fs::read_to_string(git_dir.join("HEAD"))
            .ok()
            .and_then(|head| head.trim().strip_prefix("ref: ").map(str::to_owned))
        {
            watched.push(common.join(branch));
        }
    }
    for path in watched.into_iter().filter(|p| p.exists()) {
        println!("cargo:rerun-if-changed={}", path.display());
    }
}
