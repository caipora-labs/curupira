//! OpenCode CLI adapter.

use crate::agents::profile::{bool_extra, opt_str};
use crate::agents::{AgentRequest, InteractiveLaunch};
use crate::config::AgentProfile;
use crate::error::CurupiraError;

pub(crate) fn build_headless(
    profile: &AgentProfile,
    request: &AgentRequest,
) -> Result<Vec<String>, CurupiraError> {
    let mut args = vec!["run".into(), "--format".into(), "json".into()];
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
