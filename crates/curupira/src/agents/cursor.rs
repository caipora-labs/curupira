//! Cursor (`agent`) CLI adapter.

use crate::agents::profile::{bool_extra, opt_str, reject_keys};
use crate::agents::{AgentRequest, InteractiveLaunch};
use crate::config::AgentProfile;
use crate::error::CurupiraError;

pub(crate) fn build_headless(
    profile: &AgentProfile,
    request: &AgentRequest,
) -> Result<Vec<String>, CurupiraError> {
    reject_keys(profile, &["effort"], "Cursor")?;
    let mut args = vec![
        "--print".into(),
        "--output-format".into(),
        "stream-json".into(),
    ];
    if let Some(session) = &request.session_id {
        args.extend(["--resume".into(), session.clone()]);
    }
    push_pair(&mut args, "--mode", opt_str(profile, "agent")?);
    push_pair(&mut args, "--model", opt_str(profile, "model")?);
    if bool_extra(profile, "force", false)? {
        args.push("--force".into());
    }
    if bool_extra(profile, "trust", false)? {
        args.push("--trust".into());
    }
    args.push("--".into());
    args.push(request.message.clone());
    Ok(args)
}

pub(crate) fn build_interactive(
    profile: &AgentProfile,
    model: Option<&str>,
    prompt: Option<&str>,
) -> Result<InteractiveLaunch, CurupiraError> {
    reject_keys(profile, &["effort"], "Cursor")?;
    let mut args = Vec::new();
    let mut notes = Vec::new();
    match opt_str(profile, "agent")?.as_deref() {
        Some("plan" | "ask") => {
            push_pair(&mut args, "--mode", opt_str(profile, "agent")?);
        }
        Some("agent") => {
            notes.push(
                "profile agent='agent' omits --mode; Cursor defaults to agent mode when --mode is unset"
                    .into(),
            );
        }
        Some(other) => {
            args.extend(["--mode".into(), other.into()]);
        }
        None => {}
    }
    if let Some(model) = model {
        args.extend(["--model".into(), model.into()]);
    }
    if bool_extra(profile, "force", false)? {
        args.push("--force".into());
    }
    if let Some(prompt) = prompt {
        args.push("--".into());
        args.push(prompt.into());
    }
    Ok(InteractiveLaunch {
        program: "agent".into(),
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
