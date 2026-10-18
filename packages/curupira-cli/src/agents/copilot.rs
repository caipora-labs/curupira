//! GitHub Copilot CLI adapter.

use crate::agents::profile::{bool_extra, opt_str, string_list};
use crate::agents::{AgentRequest, InteractiveLaunch};
use crate::config::AgentProfile;
use crate::error::CurupiraError;

pub(crate) fn build_headless(
    profile: &AgentProfile,
    request: &AgentRequest,
) -> Result<Vec<String>, CurupiraError> {
    let session_id = request
        .new_session_id
        .as_ref()
        .or(request.session_id.as_ref())
        .ok_or_else(|| {
            CurupiraError::Dispatch("GitHub Copilot CLI requires a session identifier".into())
        })?;

    let allow_tools = string_list(profile, "allow_tools")?;
    let deny_tools = string_list(profile, "deny_tools")?;
    validate_tool_patterns(&allow_tools)?;
    validate_tool_patterns(&deny_tools)?;

    let mut args = vec![
        "--output-format=json".into(),
        "--no-ask-user".into(),
        format!("--session-id={session_id}"),
    ];
    push_eq(&mut args, "--model", opt_str(profile, "model")?);
    push_eq(&mut args, "--agent", opt_str(profile, "agent")?);
    push_eq(&mut args, "--reasoning-effort", opt_str(profile, "effort")?);
    if bool_extra(profile, "allow_all_tools", false)? {
        args.push("--allow-all-tools".into());
    }
    if !allow_tools.is_empty() {
        args.push(format!("--allow-tool={}", allow_tools.join(",")));
    }
    if !deny_tools.is_empty() {
        args.push(format!("--deny-tool={}", deny_tools.join(",")));
    }
    args.push(format!("--prompt={}", request.message));
    Ok(args)
}

pub(crate) fn build_interactive(
    profile: &AgentProfile,
    model: Option<&str>,
    prompt: Option<&str>,
) -> Result<InteractiveLaunch, CurupiraError> {
    let allow_tools = string_list(profile, "allow_tools")?;
    let deny_tools = string_list(profile, "deny_tools")?;
    validate_tool_patterns(&allow_tools)?;
    validate_tool_patterns(&deny_tools)?;

    let mut args = Vec::new();
    if let Some(model) = model {
        args.push(format!("--model={model}"));
    }
    push_eq(&mut args, "--agent", opt_str(profile, "agent")?);
    push_eq(&mut args, "--reasoning-effort", opt_str(profile, "effort")?);
    if bool_extra(profile, "allow_all_tools", false)? {
        args.push("--allow-all-tools".into());
    }
    if !allow_tools.is_empty() {
        args.push(format!("--allow-tool={}", allow_tools.join(",")));
    }
    if !deny_tools.is_empty() {
        args.push(format!("--deny-tool={}", deny_tools.join(",")));
    }
    if let Some(prompt) = prompt {
        args.push(format!("--interactive={prompt}"));
    }
    Ok(InteractiveLaunch {
        program: "copilot".into(),
        args,
        env: vec![],
        notes: vec![],
    })
}

fn validate_tool_patterns(tools: &[String]) -> Result<(), CurupiraError> {
    if tools.iter().any(|t| t.contains(',')) {
        return Err(CurupiraError::Config(
            "Copilot tool entries must not contain commas".into(),
        ));
    }
    Ok(())
}

fn push_eq(args: &mut Vec<String>, flag: &str, value: Option<String>) {
    if let Some(value) = value {
        args.push(format!("{flag}={value}"));
    }
}
