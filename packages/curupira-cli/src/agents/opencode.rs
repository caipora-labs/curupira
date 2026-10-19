//! OpenCode CLI adapter.
//!
//! OpenCode 1.x and 2.x do not share a flag set. `api = "auto"` (the default) runs
//! `opencode --version` once per resolved binary and caches the major for the process.

use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::Duration;

use crate::agents::profile::{bool_extra, opt_str};
use crate::agents::{AgentRequest, InteractiveLaunch};
use crate::config::AgentProfile;
use crate::error::CurupiraError;
use crate::process::{capture_sync, resolve_executable};

/// Which OpenCode command line to build.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum OpenCodeCli {
    V1,
    V2,
}

static VERSION_CACHE: Mutex<Option<HashMap<PathBuf, OpenCodeCli>>> = Mutex::new(None);

/// `None` means detect from `opencode --version`.
pub(crate) fn configured_cli(profile: &AgentProfile) -> Result<Option<OpenCodeCli>, CurupiraError> {
    match opt_str(profile, "api")?.as_deref() {
        None | Some("auto") => Ok(None),
        Some("v1") => Ok(Some(OpenCodeCli::V1)),
        Some("v2") => Ok(Some(OpenCodeCli::V2)),
        Some(other) => Err(CurupiraError::Config(format!(
            "profile field \"api\" must be \"v1\", \"v2\", or \"auto\", got {other:?}"
        ))),
    }
}

/// First `major.minor.patch` in `opencode --version` output.
///
/// 2.x prints `opencode v2.0.32`. 1.x prints `1.19.3`.
#[must_use]
pub(crate) fn parse_opencode_major(text: &str) -> Option<u32> {
    let bytes = text.as_bytes();
    let mut i = 0;
    while i < bytes.len() {
        if !bytes[i].is_ascii_digit() {
            i += 1;
            continue;
        }
        let start = i;
        i = scan_digits(bytes, i);
        let major_end = i;
        if !eat_dot(bytes, &mut i) {
            continue;
        }
        let minor_start = i;
        i = scan_digits(bytes, i);
        if i == minor_start || !eat_dot(bytes, &mut i) {
            continue;
        }
        let patch_start = i;
        i = scan_digits(bytes, i);
        if i == patch_start {
            continue;
        }
        let Ok(text) = std::str::from_utf8(&bytes[start..major_end]) else {
            continue;
        };
        let Ok(major) = text.parse::<u32>() else {
            continue;
        };
        return Some(major);
    }
    None
}

fn scan_digits(bytes: &[u8], mut i: usize) -> usize {
    while i < bytes.len() && bytes[i].is_ascii_digit() {
        i += 1;
    }
    i
}

fn eat_dot(bytes: &[u8], i: &mut usize) -> bool {
    if *i < bytes.len() && bytes[*i] == b'.' {
        *i += 1;
        true
    } else {
        false
    }
}

fn cli_from_major(major: u32) -> Result<OpenCodeCli, CurupiraError> {
    match major {
        1 => Ok(OpenCodeCli::V1),
        major if major >= 2 => Ok(OpenCodeCli::V2),
        other => Err(CurupiraError::Dispatch(format!(
            "OpenCode version {other}.x is not supported. Set profile field api to \"v1\" or \"v2\"."
        ))),
    }
}

/// Resolve `auto` by running `<program> --version` once per executable path.
pub(crate) fn detect_cli(program: &str) -> Result<OpenCodeCli, CurupiraError> {
    let path = resolve_executable(program).map_err(|_| {
        CurupiraError::Dispatch(format!(
            "coding-agent executable {program:?} not found on PATH (provider opencode)"
        ))
    })?;
    if let Some(cli) = VERSION_CACHE
        .lock()
        .unwrap_or_else(|err| err.into_inner())
        .get_or_insert_with(HashMap::new)
        .get(&path)
        .copied()
    {
        return Ok(cli);
    }
    let cli = probe_cli(&path)?;
    VERSION_CACHE
        .lock()
        .unwrap_or_else(|err| err.into_inner())
        .get_or_insert_with(HashMap::new)
        .insert(path, cli);
    Ok(cli)
}

fn probe_cli(path: &Path) -> Result<OpenCodeCli, CurupiraError> {
    let program = path.to_string_lossy();
    let result = capture_sync(&program, &["--version".into()], Duration::from_secs(10))
        .map_err(|err| version_error(path, &err))?;
    let stdout = String::from_utf8_lossy(&result.stdout);
    let stderr = String::from_utf8_lossy(&result.stderr);
    let combined = format!("{stdout}\n{stderr}");
    if let Some(major) = parse_opencode_major(&combined) {
        return cli_from_major(major);
    }
    let detail = if result.exit_code == 0 {
        format!("output {combined:?} has no x.y.z version")
    } else {
        format!("exit {}: {combined:?}", result.exit_code)
    };
    Err(version_error(path, &detail))
}

fn version_error(path: &Path, detail: &str) -> CurupiraError {
    CurupiraError::Dispatch(format!(
        "could not detect the OpenCode CLI major version from `{} --version` ({detail}). Set profile field api to \"v1\" or \"v2\".",
        path.display()
    ))
}

pub(crate) fn build_headless(
    profile: &AgentProfile,
    request: &AgentRequest,
    cli: OpenCodeCli,
) -> Result<Vec<String>, CurupiraError> {
    match cli {
        OpenCodeCli::V1 => build_headless_v1(profile, request),
        OpenCodeCli::V2 => build_headless_v2(profile, request),
    }
}

fn build_headless_v1(
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

fn build_headless_v2(
    profile: &AgentProfile,
    request: &AgentRequest,
) -> Result<Vec<String>, CurupiraError> {
    let mut args = vec![
        "run".into(),
        "--standalone".into(),
        "--format".into(),
        "json".into(),
    ];
    if let Some(session) = &request.session_id {
        args.extend(["--session".into(), session.clone()]);
    }
    let model = v2_model(profile, None)?;
    if model.ignored_effort {
        tracing::warn!(
            "OpenCode 2.x ignores profile effort when model is not set; the variant belongs in --model provider/model#variant"
        );
    }
    push_pair(&mut args, "--model", model.value);
    push_pair(&mut args, "--agent", opt_str(profile, "agent")?);
    if bool_extra(profile, "auto_approve", false)? {
        args.push("--auto".into());
    }
    args.push("--".into());
    args.push(request.message.clone());
    Ok(args)
}

/// OpenCode 1.x keeps sessions and its project registry in one database. The registry is keyed
/// by the repository's root commit, so clones of the same repository share it. Each 1.x task
/// gets its own database next to its worktree, so the agent never reuses a session or project
/// entry that points at another checkout. The path is derived from the worktree, so `--session`
/// resumes still find the same database.
///
/// OpenCode 2.x also stores provider credentials in that database, so a fresh one has no model
/// routes ("Model unavailable"). 2.x tasks keep the user's database; `--standalone` already
/// gives each task a private server rooted at its worktree.
pub(crate) fn headless_env(cwd: &Path, cli: OpenCodeCli) -> Vec<(String, String)> {
    if cli == OpenCodeCli::V2 {
        return Vec::new();
    }
    let mut db = cwd.as_os_str().to_owned();
    db.push(".opencode.db");
    let db = PathBuf::from(db);
    vec![("OPENCODE_DB".into(), db.to_string_lossy().into_owned())]
}

/// Lists recent sessions of the worktree's project as JSON, for reading the title OpenCode
/// generates for a session a few seconds after it starts. Read-only; 2.x uses a private server
/// like the run itself, so no background service is left behind.
pub(crate) fn build_session_list(cli: OpenCodeCli) -> Vec<String> {
    let mut args = vec!["session".to_string(), "list".into()];
    if cli == OpenCodeCli::V2 {
        args.push("--standalone".into());
    }
    args.extend(["--format".into(), "json".into(), "-n".into(), "50".into()]);
    args
}

/// The generated title of `session_id` in `session list --format json` output. New sessions
/// have no title yet (2.x) or a `New session - <timestamp>` placeholder (1.x).
pub(crate) fn session_title(list: &str, session_id: &str) -> Option<String> {
    let sessions: Vec<serde_json::Value> = serde_json::from_str(list).ok()?;
    let title = sessions
        .iter()
        .find(|s| s.get("id").and_then(serde_json::Value::as_str) == Some(session_id))?
        .get("title")?
        .as_str()?
        .trim();
    let placeholder = ["New session - ", "Child session - "]
        .iter()
        .any(|prefix| title.starts_with(prefix));
    (!title.is_empty() && !placeholder).then(|| title.to_owned())
}

pub(crate) fn build_interactive(
    profile: &AgentProfile,
    model: Option<&str>,
    prompt: Option<&str>,
    cli: OpenCodeCli,
) -> Result<InteractiveLaunch, CurupiraError> {
    match cli {
        OpenCodeCli::V1 => build_interactive_v1(profile, model, prompt),
        OpenCodeCli::V2 => build_interactive_v2(profile, model, prompt),
    }
}

fn build_interactive_v1(
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

fn build_interactive_v2(
    profile: &AgentProfile,
    model: Option<&str>,
    prompt: Option<&str>,
) -> Result<InteractiveLaunch, CurupiraError> {
    let mut args = Vec::new();
    let mut notes = Vec::new();
    let selected = v2_model(profile, model)?;
    if selected.ignored_effort {
        notes.push(
            "profile effort is ignored because OpenCode 2.x puts the variant in --model provider/model#variant and no model is set"
                .into(),
        );
    }
    push_pair(&mut args, "--model", selected.value);
    push_pair(&mut args, "--agent", opt_str(profile, "agent")?);
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

struct SelectedModel {
    value: Option<String>,
    ignored_effort: bool,
}

/// 2.x takes the reasoning variant inside `--model provider/model#variant`.
fn v2_model(
    profile: &AgentProfile,
    override_model: Option<&str>,
) -> Result<SelectedModel, CurupiraError> {
    let model = match override_model {
        Some(model) => Some(model.to_string()),
        None => opt_str(profile, "model")?,
    };
    let effort = opt_str(profile, "effort")?;
    match (model, effort) {
        (Some(model), Some(_effort)) if model.contains('#') => Err(CurupiraError::Config(
            "profile field \"effort\" cannot be combined with a model that already includes a #variant"
                .into(),
        )),
        (Some(model), Some(effort)) => Ok(SelectedModel {
            value: Some(format!("{model}#{effort}")),
            ignored_effort: false,
        }),
        (Some(model), None) => Ok(SelectedModel {
            value: Some(model),
            ignored_effort: false,
        }),
        (None, Some(_)) => Ok(SelectedModel {
            value: None,
            ignored_effort: true,
        }),
        (None, None) => Ok(SelectedModel {
            value: None,
            ignored_effort: false,
        }),
    }
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
    use serde_json::json;

    fn profile() -> AgentProfile {
        AgentProfile {
            provider: "opencode".into(),
            extra: serde_json::Map::new(),
        }
    }

    fn profile_with(extra: serde_json::Map<String, serde_json::Value>) -> AgentProfile {
        AgentProfile {
            provider: "opencode".into(),
            extra,
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
        let args = build_headless(
            &profile(),
            &request("/ws/repo.worktrees/auto/task"),
            OpenCodeCli::V1,
        )
        .unwrap();

        let dir = args
            .iter()
            .position(|a| a == "--dir")
            .expect("--dir is passed");
        assert_eq!(args[dir + 1], "/ws/repo.worktrees/auto/task");
    }

    #[test]
    fn task_database_sits_next_to_the_worktree_and_keeps_dots_in_the_path() {
        let env = headless_env(
            Path::new("/ws/gh.dispatch.worktrees/auto/task"),
            OpenCodeCli::V1,
        );

        assert_eq!(
            env,
            vec![(
                "OPENCODE_DB".to_string(),
                "/ws/gh.dispatch.worktrees/auto/task.opencode.db".to_string()
            )]
        );
    }

    #[test]
    fn v2_tasks_keep_the_user_database_with_its_credentials() {
        assert!(
            headless_env(Path::new("/ws/repo.worktrees/auto/task"), OpenCodeCli::V2).is_empty()
        );
    }

    #[test]
    fn session_list_matches_the_run_mode() {
        assert_eq!(
            build_session_list(OpenCodeCli::V2),
            vec![
                "session",
                "list",
                "--standalone",
                "--format",
                "json",
                "-n",
                "50"
            ]
        );
        assert_eq!(
            build_session_list(OpenCodeCli::V1),
            vec!["session", "list", "--format", "json", "-n", "50"]
        );
    }

    #[test]
    fn session_title_skips_missing_and_placeholder_titles() {
        let list = r#"[
            {"id": "ses_a", "title": "Revisão do PR #223", "directory": "/w"},
            {"id": "ses_b", "directory": "/w"},
            {"id": "ses_c", "title": "New session - 2026-10-19T03:40:00.000Z"},
            {"id": "ses_d", "title": "  "}
        ]"#;
        assert_eq!(
            session_title(list, "ses_a").as_deref(),
            Some("Revisão do PR #223")
        );
        assert_eq!(session_title(list, "ses_b"), None);
        assert_eq!(session_title(list, "ses_c"), None);
        assert_eq!(session_title(list, "ses_d"), None);
        assert_eq!(session_title(list, "ses_missing"), None);
        assert_eq!(session_title("not json", "ses_a"), None);
    }

    #[test]
    fn parses_both_version_banners() {
        assert_eq!(parse_opencode_major("opencode v2.0.32"), Some(2));
        assert_eq!(parse_opencode_major("1.19.3\n"), Some(1));
        assert_eq!(parse_opencode_major("see 10.0.1 then 3.1.4"), Some(10));
        assert_eq!(parse_opencode_major("v2"), None);
        assert_eq!(parse_opencode_major(""), None);
    }

    #[test]
    fn api_field_accepts_only_v1_v2_auto() {
        assert_eq!(configured_cli(&profile()).unwrap(), None);
        let mut extra = serde_json::Map::new();
        extra.insert("api".into(), json!("auto"));
        assert_eq!(configured_cli(&profile_with(extra.clone())).unwrap(), None);
        extra.insert("api".into(), json!("v1"));
        assert_eq!(
            configured_cli(&profile_with(extra.clone())).unwrap(),
            Some(OpenCodeCli::V1)
        );
        extra.insert("api".into(), json!("v2"));
        assert_eq!(
            configured_cli(&profile_with(extra.clone())).unwrap(),
            Some(OpenCodeCli::V2)
        );
        extra.insert("api".into(), json!("v3"));
        let err = configured_cli(&profile_with(extra)).unwrap_err();
        assert!(err.to_string().contains("api"), "{err}");
    }

    #[test]
    fn v2_headless_drops_dir_and_folds_effort_into_the_model() {
        let mut extra = serde_json::Map::new();
        extra.insert("model".into(), json!("anthropic/claude-sonnet-4"));
        extra.insert("agent".into(), json!("build"));
        extra.insert("effort".into(), json!("high"));
        extra.insert("auto_approve".into(), json!(true));
        let args = build_headless(
            &profile_with(extra),
            &AgentRequest {
                message: "fix".into(),
                cwd: PathBuf::from("/ws/task"),
                session_id: Some("ses_1".into()),
                new_session_id: None,
            },
            OpenCodeCli::V2,
        )
        .unwrap();
        assert_eq!(
            args,
            vec![
                "run",
                "--standalone",
                "--format",
                "json",
                "--session",
                "ses_1",
                "--model",
                "anthropic/claude-sonnet-4#high",
                "--agent",
                "build",
                "--auto",
                "--",
                "fix",
            ]
        );
        assert!(!args.iter().any(|arg| arg == "--dir" || arg == "--variant"));
    }

    #[test]
    fn v2_effort_without_model_is_omitted() {
        let mut extra = serde_json::Map::new();
        extra.insert("effort".into(), json!("high"));
        let args = build_headless(
            &profile_with(extra.clone()),
            &request("/ws"),
            OpenCodeCli::V2,
        )
        .unwrap();
        assert!(!args.iter().any(|arg| arg == "--model" || arg == "high"));

        let launch = build_interactive(&profile_with(extra), None, None, OpenCodeCli::V2).unwrap();
        assert!(launch.notes.iter().any(|note| note.contains("effort")));
        assert!(!launch.args.iter().any(|arg| arg == "--model"));
    }

    #[test]
    fn v2_rejects_effort_when_the_model_already_has_a_variant() {
        let mut extra = serde_json::Map::new();
        extra.insert("model".into(), json!("openai/gpt-5.2#low"));
        extra.insert("effort".into(), json!("high"));
        let err =
            build_headless(&profile_with(extra), &request("/ws"), OpenCodeCli::V2).unwrap_err();
        assert!(err.to_string().contains("effort"), "{err}");
    }

    #[test]
    fn v2_interactive_folds_effort_into_the_model_override() {
        let mut extra = serde_json::Map::new();
        extra.insert("effort".into(), json!("max"));
        extra.insert("agent".into(), json!("build"));
        let launch = build_interactive(
            &profile_with(extra),
            Some("openai/gpt-5.2"),
            Some("look"),
            OpenCodeCli::V2,
        )
        .unwrap();
        assert_eq!(
            launch.args,
            vec![
                "--model",
                "openai/gpt-5.2#max",
                "--agent",
                "build",
                "--prompt=look",
            ]
        );
        assert!(launch.notes.is_empty());
    }

    #[test]
    fn v1_interactive_still_skips_effort() {
        let mut extra = serde_json::Map::new();
        extra.insert("effort".into(), json!("high"));
        let launch =
            build_interactive(&profile_with(extra), Some("p/m"), None, OpenCodeCli::V1).unwrap();
        assert_eq!(launch.args, vec!["--model", "p/m"]);
        assert!(launch.notes.iter().any(|note| note.contains("--variant")));
    }

    #[cfg(unix)]
    #[test]
    fn detects_major_from_the_binary_and_caches_it() {
        let dir = tempfile::tempdir().unwrap();
        let bin = dir.path().join("opencode");
        std::fs::write(&bin, "#!/bin/sh\nprintf '%s\\n' 'opencode v2.0.32'\n").unwrap();
        std::fs::set_permissions(&bin, std::os::unix::fs::PermissionsExt::from_mode(0o755))
            .unwrap();

        let old = std::env::var_os("PATH");
        let mut parts = vec![dir.path().to_path_buf()];
        if let Some(value) = &old {
            parts.extend(std::env::split_paths(value));
        }
        std::env::set_var("PATH", std::env::join_paths(&parts).unwrap());
        let detected = detect_cli("opencode");
        std::fs::write(&bin, "#!/bin/sh\nprintf '%s\\n' '1.0.0'\n").unwrap();
        let cached = detect_cli("opencode");
        match &old {
            Some(value) => std::env::set_var("PATH", value),
            None => std::env::remove_var("PATH"),
        }
        assert_eq!(detected.unwrap(), OpenCodeCli::V2);
        assert_eq!(cached.unwrap(), OpenCodeCli::V2);
    }

    #[test]
    fn undetectable_version_asks_for_an_explicit_api() {
        let err = detect_cli("curupira-no-such-opencode").unwrap_err();
        let text = err.to_string();
        assert!(text.contains("not found on PATH"), "{text}");
    }
}
