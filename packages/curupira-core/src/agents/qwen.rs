//! Qwen Code CLI adapter.

use crate::agents::profile::{opt_str, opt_u64, reject_keys};
use crate::agents::{AgentRequest, InteractiveLaunch};
use crate::config::AgentProfile;
use crate::error::CurupiraError;

pub(crate) fn build_headless(
    profile: &AgentProfile,
    request: &AgentRequest,
) -> Result<Vec<String>, CurupiraError> {
    reject_keys(profile, &["agent", "effort"], "Qwen Code")?;
    let mut args = vec!["--output-format".into(), "stream-json".into()];
    if let Some(session) = &request.session_id {
        args.extend(["--resume".into(), session.clone()]);
    }
    push_pair(&mut args, "--model", opt_str(profile, "model")?);
    push_pair(
        &mut args,
        "--approval-mode",
        opt_str(profile, "approval_mode")?,
    );
    if let Some(turns) = opt_u64(profile, "max_session_turns")? {
        args.extend(["--max-session-turns".into(), turns.to_string()]);
    }
    args.push(format!("--prompt={}", request.message));
    Ok(args)
}

pub(crate) fn build_interactive(
    profile: &AgentProfile,
    model: Option<&str>,
    prompt: Option<&str>,
) -> Result<InteractiveLaunch, CurupiraError> {
    reject_keys(profile, &["agent", "effort"], "Qwen Code")?;
    let mut args = Vec::new();
    let mut notes = Vec::new();
    if let Some(model) = model {
        args.extend(["--model".into(), model.into()]);
    }
    push_pair(
        &mut args,
        "--approval-mode",
        opt_str(profile, "approval_mode")?,
    );
    if let Some(turns) = opt_u64(profile, "max_session_turns")? {
        args.extend(["--max-session-turns".into(), turns.to_string()]);
        notes.push(
            "--max-session-turns is documented as a headless run budget; its effect in an interactive session is unconfirmed"
                .into(),
        );
    }
    if let Some(prompt) = prompt {
        args.push(format!("--prompt-interactive={prompt}"));
    }
    Ok(InteractiveLaunch {
        program: "qwen".into(),
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
