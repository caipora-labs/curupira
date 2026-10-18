//! pi coding-agent CLI adapter.

use crate::agents::profile::{opt_bool, opt_str, reject_keys, string_list};
use crate::agents::{AgentRequest, InteractiveLaunch};
use crate::config::AgentProfile;
use crate::error::CurupiraError;

pub(crate) fn build_headless(
    profile: &AgentProfile,
    request: &AgentRequest,
) -> Result<Vec<String>, CurupiraError> {
    reject_keys(profile, &["agent"], "pi")?;
    let model_provider = opt_str(profile, "model_provider")?;
    let model = opt_str(profile, "model")?;
    if model_provider.is_some() && model.is_none() {
        return Err(CurupiraError::Config(
            "model_provider requires model".into(),
        ));
    }

    let mut args = vec!["--mode".into(), "json".into()];
    if let Some(session) = &request.session_id {
        args.extend(["--session".into(), session.clone()]);
    }
    push_pair(&mut args, "--provider", model_provider);
    push_pair(&mut args, "--model", model);
    push_pair(&mut args, "--thinking", opt_str(profile, "effort")?);
    let tools = string_list(profile, "tools")?;
    if !tools.is_empty() {
        args.extend(["--tools".into(), tools.join(",")]);
    }
    let exclude = string_list(profile, "exclude_tools")?;
    if !exclude.is_empty() {
        args.extend(["--exclude-tools".into(), exclude.join(",")]);
    }
    match opt_bool(profile, "approve")? {
        Some(true) => args.push("--approve".into()),
        Some(false) => args.push("--no-approve".into()),
        None => {}
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
    reject_keys(profile, &["agent"], "pi")?;
    let mut args = Vec::new();
    let mut notes = Vec::new();
    let profile_model = opt_str(profile, "model")?;
    let model_provider = opt_str(profile, "model_provider")?;
    if let Some(model) = model {
        if model_provider.is_some() && profile_model.as_deref() == Some(model) {
            push_pair(&mut args, "--provider", model_provider);
        }
        args.extend(["--model".into(), model.into()]);
    }
    push_pair(&mut args, "--thinking", opt_str(profile, "effort")?);
    let tools = string_list(profile, "tools")?;
    if !tools.is_empty() {
        args.extend(["--tools".into(), tools.join(",")]);
    }
    let exclude = string_list(profile, "exclude_tools")?;
    if !exclude.is_empty() {
        args.extend(["--exclude-tools".into(), exclude.join(",")]);
    }
    match opt_bool(profile, "approve")? {
        Some(true) => args.push("--approve".into()),
        Some(false) => args.push("--no-approve".into()),
        None => {}
    }
    if let Some(prompt) = prompt {
        args.push("--".into());
        args.push(prompt.into());
        notes.push("initial prompt uses the -- terminator, which requires pi >= 1.x".into());
    }
    Ok(InteractiveLaunch {
        program: "pi".into(),
        args,
        env: vec![],
        notes,
    })
}

pub(crate) fn session_id_from_line(line: &str) -> Option<String> {
    let value: serde_json::Value = serde_json::from_str(line.trim()).ok()?;
    if value.get("type").and_then(|v| v.as_str()) != Some("session") {
        return None;
    }
    value
        .get("id")
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
