//! Claude Code CLI adapter.

use crate::agents::profile::opt_str;
use crate::agents::{AgentRequest, InteractiveLaunch};
use crate::config::AgentProfile;
use crate::error::CurupiraError;

pub(crate) fn build_headless(
    profile: &AgentProfile,
    request: &AgentRequest,
) -> Result<Vec<String>, CurupiraError> {
    let mut args = vec![
        "-p".into(),
        "--output-format".into(),
        "stream-json".into(),
        "--verbose".into(),
    ];
    if let Some(session) = &request.session_id {
        args.extend(["--resume".into(), session.clone()]);
    }
    push_pair(&mut args, "--model", opt_str(profile, "model")?);
    push_pair(&mut args, "--agent", opt_str(profile, "agent")?);
    push_pair(&mut args, "--effort", opt_str(profile, "effort")?);
    push_pair(
        &mut args,
        "--permission-mode",
        opt_str(profile, "permission_mode")?,
    );
    push_pair(
        &mut args,
        "--permission-prompts",
        opt_str(profile, "permission_prompts")?,
    );
    args.push("--".into());
    args.push(request.message.clone());
    Ok(args)
}

pub(crate) fn build_interactive(
    profile: &AgentProfile,
    model: Option<&str>,
    prompt: Option<&str>,
) -> Result<InteractiveLaunch, CurupiraError> {
    let mut args = Vec::new();
    if let Some(model) = model {
        args.extend(["--model".into(), model.into()]);
    }
    push_pair(&mut args, "--agent", opt_str(profile, "agent")?);
    push_pair(&mut args, "--effort", opt_str(profile, "effort")?);
    push_pair(
        &mut args,
        "--permission-mode",
        opt_str(profile, "permission_mode")?,
    );
    if let Some(prompt) = prompt {
        args.push("--".into());
        args.push(prompt.into());
    }
    Ok(InteractiveLaunch {
        program: "claude".into(),
        args,
        env: vec![],
        notes: vec![],
    })
}

fn push_pair(args: &mut Vec<String>, flag: &str, value: Option<String>) {
    if let Some(value) = value {
        args.push(flag.into());
        args.push(value);
    }
}
