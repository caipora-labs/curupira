//! A headless agent launch runs inside its task worktree with its own OpenCode database.
//!
//! The "agent" is a shell script that records its environment. No coding-agent CLI runs here.

#![cfg(unix)]

use std::fs;
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;
use std::time::Duration;

use curupira::agents::{build_headless, AgentProvider, AgentRequest};
use curupira::config::AgentProfile;
use curupira::process::run_process;

#[tokio::test]
async fn opencode_task_runs_in_its_worktree_with_its_own_database() {
    let root = tempfile::tempdir().unwrap();
    let worktree = root.path().join("repo.worktrees/auto/task");
    fs::create_dir_all(&worktree).unwrap();

    let fake = root.path().join("fake-opencode");
    fs::write(
        &fake,
        "#!/bin/sh\nprintf '%s\\n%s\\n%s\\n' \"$PWD\" \"$OPENCODE_DB\" \"$*\"\n",
    )
    .unwrap();
    fs::set_permissions(&fake, fs::Permissions::from_mode(0o755)).unwrap();

    let profile = AgentProfile {
        provider: "opencode".into(),
        extra: serde_json::Map::new(),
    };
    let request = AgentRequest {
        message: "resolve".into(),
        cwd: worktree.clone(),
        session_id: None,
        new_session_id: None,
    };
    let launch = build_headless(AgentProvider::OpenCode, &profile, &request).unwrap();

    let result = run_process(
        fake.to_str().unwrap(),
        &launch.args,
        Some(&worktree),
        &launch.env,
        Duration::from_secs(10),
        4096,
    )
    .await
    .unwrap();

    assert_eq!(result.exit_code, 0);
    let stdout = String::from_utf8(result.stdout).unwrap();
    let mut lines = stdout.lines();
    let pwd = PathBuf::from(lines.next().unwrap()).canonicalize().unwrap();
    assert_eq!(pwd, worktree.canonicalize().unwrap());
    assert_eq!(
        lines.next().unwrap(),
        format!("{}.opencode.db", worktree.display())
    );
    let argv = lines.next().unwrap();
    assert!(
        argv.contains(&format!("--dir {}", worktree.display())),
        "argv was {argv:?}"
    );
}
