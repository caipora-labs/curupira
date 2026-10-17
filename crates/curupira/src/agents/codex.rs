//! Codex CLI adapter.

use crate::agents::profile::{bool_extra, opt_str};
use crate::agents::{AgentRequest, InteractiveLaunch};
use crate::config::AgentProfile;
use crate::error::CurupiraError;

pub(crate) fn build_headless(
    profile: &AgentProfile,
    request: &AgentRequest,
) -> Result<Vec<String>, CurupiraError> {
    let mut args = vec!["exec".into()];
    if let Some(session) = &request.session_id {
        args.extend(["resume".into(), session.clone()]);
    }
    push_pair(&mut args, "--model", opt_str(profile, "model")?);
    push_pair(&mut args, "--profile", opt_str(profile, "agent")?);
    if let Some(effort) = opt_str(profile, "effort")? {
        let encoded =
            serde_json::to_string(&effort).map_err(|e| CurupiraError::Dispatch(e.to_string()))?;
        args.extend([
            "--config".into(),
            format!("model_reasoning_effort={encoded}"),
        ]);
    }
    push_pair(&mut args, "--sandbox", opt_str(profile, "sandbox")?);
    if bool_extra(profile, "auto_review", false)? {
        args.extend([
            "--config".into(),
            "approval_policy=\"on-request\"".into(),
            "--config".into(),
            "approvals_reviewer=\"auto_review\"".into(),
        ]);
    }
    args.extend(["--json".into(), "--".into(), request.message.clone()]);
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
    push_pair(&mut args, "--profile", opt_str(profile, "agent")?);
    if let Some(effort) = opt_str(profile, "effort")? {
        let encoded =
            serde_json::to_string(&effort).map_err(|e| CurupiraError::Dispatch(e.to_string()))?;
        args.extend([
            "--config".into(),
            format!("model_reasoning_effort={encoded}"),
        ]);
        notes.push(
            "model_reasoning_effort is passed via --config; the Codex reference documents --config but not this key name"
                .into(),
        );
    }
    push_pair(&mut args, "--sandbox", opt_str(profile, "sandbox")?);
    if bool_extra(profile, "auto_review", false)? {
        args.extend([
            "--config".into(),
            "approval_policy=\"on-request\"".into(),
            "--config".into(),
            "approvals_reviewer=\"auto_review\"".into(),
        ]);
        notes.push(
            "auto_review approval_policy/approvals_reviewer --config keys are copied from the headless mapping"
                .into(),
        );
    }
    if let Some(prompt) = prompt {
        args.push("--".into());
        args.push(prompt.into());
    }
    Ok(InteractiveLaunch {
        program: "codex".into(),
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
