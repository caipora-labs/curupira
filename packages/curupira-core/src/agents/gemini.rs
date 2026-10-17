//! Gemini CLI adapter.

use crate::agents::profile::{bool_extra, opt_str, reject_keys};
use crate::agents::{AgentRequest, InteractiveLaunch};
use crate::config::AgentProfile;
use crate::error::CurupiraError;

pub(crate) fn build_headless(
    profile: &AgentProfile,
    request: &AgentRequest,
) -> Result<Vec<String>, CurupiraError> {
    reject_keys(profile, &["agent", "effort"], "Gemini CLI")?;
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
    if bool_extra(profile, "skip_trust", false)? {
        args.push("--skip-trust".into());
    }
    args.push(format!("--prompt={}", request.message));
    Ok(args)
}

pub(crate) fn build_interactive(
    profile: &AgentProfile,
    model: Option<&str>,
    prompt: Option<&str>,
) -> Result<InteractiveLaunch, CurupiraError> {
    reject_keys(profile, &["agent", "effort"], "Gemini CLI")?;
    let mut args = Vec::new();
    if let Some(model) = model {
        args.extend(["--model".into(), model.into()]);
    }
    push_pair(
        &mut args,
        "--approval-mode",
        opt_str(profile, "approval_mode")?,
    );
    if bool_extra(profile, "skip_trust", false)? {
        args.push("--skip-trust".into());
    }
    if let Some(prompt) = prompt {
        args.push(format!("--prompt-interactive={prompt}"));
    }
    Ok(InteractiveLaunch {
        program: "gemini".into(),
        args,
        env: vec![],
        notes: vec![],
    })
}

pub(crate) fn session_id_from_line(line: &str) -> Option<String> {
    let value: serde_json::Value = serde_json::from_str(line.trim()).ok()?;
    if value.get("type").and_then(|v| v.as_str()) != Some("init") {
        // Fall back to common keys for other events.
        return value
            .get("session_id")
            .or_else(|| value.get("sessionId"))
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .map(str::to_string);
    }
    value
        .get("session_id")
        .or_else(|| value.get("sessionId"))
        .and_then(|v| v.as_str())
        .filter(|s| !s.is_empty())
        .map(str::to_string)
}

fn push_pair(args: &mut Vec<String>, flag: &str, value: Option<String>) {
    if let Some(value) = value {
        args.push(flag.into());
        args.push(value);
    }
}
