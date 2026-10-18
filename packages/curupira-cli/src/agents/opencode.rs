//! OpenCode CLI adapter.

use std::path::PathBuf;

use crate::agents::profile::{bool_extra, opt_str};
use crate::agents::{AgentRequest, InteractiveLaunch};
use crate::config::AgentProfile;
use crate::error::CurupiraError;

pub(crate) fn build_headless(
    profile: &AgentProfile,
    request: &AgentRequest,
) -> Result<Vec<String>, CurupiraError> {
    let mut args = vec![
        "run".into(),
        "--format".into(),
        "json".into(),
        "--dir".into(),
        request.cwd.to_string_lossy().into_owned(),
    ];
    if let Some(session) = &request.session_id {
        args.extend(["--session".into(), session.clone()]);
    }
    push_pair(&mut args, "--model", opt_str(profile, "model")?);
    push_pair(&mut args, "--agent", opt_str(profile, "agent")?);
    push_pair(&mut args, "--variant", opt_str(profile, "effort")?);
    if bool_extra(profile, "auto_approve", false)? {
        args.push("--auto".into());
    }
    args.push("--".into());
    args.push(request.message.clone());
    Ok(args)
}

/// OpenCode keeps sessions and its project registry in one database. The registry is keyed by
/// the repository's root commit, so clones of the same repository share it. Each task gets its
/// own database next to its worktree, so the agent never reuses a session or project entry that
/// points at another checkout. The path is derived from the worktree, so `--session` resumes
/// still find the same database.
pub(crate) fn headless_env(request: &AgentRequest) -> Vec<(String, String)> {
    let mut db = request.cwd.as_os_str().to_owned();
    db.push(".opencode.db");
    let db = PathBuf::from(db);
    vec![("OPENCODE_DB".into(), db.to_string_lossy().into_owned())]
}

pub(crate) fn build_interactive(
    profile: &AgentProfile,
    model: Option<&str>,
    prompt: Option<&str>,
) -> Result<InteractiveLaunch, CurupiraError> {
    let mut args = Vec::new();
    let mut notes = Vec::new();
    if let Some(model) = model {
        args.extend(["--model".into(), model.into()]);
    }
    push_pair(&mut args, "--agent", opt_str(profile, "agent")?);
    if opt_str(profile, "effort")?.is_some() {
        notes.push(
            "profile effort is not applied interactively; --variant is documented only for opencode run"
                .into(),
        );
    }
    if let Some(prompt) = prompt {
        args.push(format!("--prompt={prompt}"));
    }
    if bool_extra(profile, "auto_approve", false)? {
        args.push("--auto".into());
    }
    Ok(InteractiveLaunch {
        program: "opencode".into(),
        args,
        env: vec![],
        notes,
    })
}

fn push_pair(args: &mut Vec<String>, flag: &str, value: Option<String>) {
    if let Some(value) = value {
        args.push(flag.into());
        args.push(value);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn profile() -> AgentProfile {
        AgentProfile {
            provider: "opencode".into(),
            extra: serde_json::Map::new(),
        }
    }

    fn request(cwd: &str) -> AgentRequest {
        AgentRequest {
            message: "work".into(),
            cwd: PathBuf::from(cwd),
            session_id: None,
            new_session_id: None,
        }
    }

    #[test]
    fn headless_run_is_pinned_to_the_task_directory() {
        let args = build_headless(&profile(), &request("/ws/repo.worktrees/auto/task")).unwrap();

        let dir = args
            .iter()
            .position(|a| a == "--dir")
            .expect("--dir is passed");
        assert_eq!(args[dir + 1], "/ws/repo.worktrees/auto/task");
    }

    #[test]
    fn task_database_sits_next_to_the_worktree_and_keeps_dots_in_the_path() {
        let env = headless_env(&request("/ws/gh.dispatch.worktrees/auto/task"));

        assert_eq!(
            env,
            vec![(
                "OPENCODE_DB".to_string(),
                "/ws/gh.dispatch.worktrees/auto/task.opencode.db".to_string()
            )]
        );
    }
}
