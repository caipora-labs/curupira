//! Built-in coding-agent adapters (argv builders) living in the Rust core.
//!
//! Extensions no longer contribute coding agents. Each provider maps a TOML
//! profile onto native CLI flags without inventing undocumented arguments.

mod claude;
mod codex;
mod copilot;
mod cursor;
mod gemini;
mod kilo;
mod opencode;
mod pi;
mod profile;
mod qwen;

use std::path::PathBuf;

use crate::config::AgentProfile;
use crate::error::CurupiraError;

pub use profile::{bool_extra, opt_str, string_list};

/// Identifiers for built-in coding-agent providers.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum AgentProvider {
    OpenCode,
    Claude,
    Codex,
    Cursor,
    Gemini,
    Copilot,
    Kilo,
    Pi,
    Qwen,
}

impl AgentProvider {
    /// Parse a configured `provider` string.
    pub fn parse(raw: &str) -> Result<Self, CurupiraError> {
        match raw {
            "opencode" => Ok(Self::OpenCode),
            "claude" => Ok(Self::Claude),
            "codex" => Ok(Self::Codex),
            "cursor" => Ok(Self::Cursor),
            "gemini" => Ok(Self::Gemini),
            "copilot" => Ok(Self::Copilot),
            "kilo" => Ok(Self::Kilo),
            "pi" => Ok(Self::Pi),
            "qwen" => Ok(Self::Qwen),
            other => Err(CurupiraError::Config(format!(
                "unknown coding-agent provider {other:?}; expected one of: {}",
                known_providers().join(", ")
            ))),
        }
    }

    /// Stable provider id used in TOML.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::OpenCode => "opencode",
            Self::Claude => "claude",
            Self::Codex => "codex",
            Self::Cursor => "cursor",
            Self::Gemini => "gemini",
            Self::Copilot => "copilot",
            Self::Kilo => "kilo",
            Self::Pi => "pi",
            Self::Qwen => "qwen",
        }
    }

    /// Native executable name on PATH.
    #[must_use]
    pub const fn executable(self) -> &'static str {
        match self {
            Self::OpenCode => "opencode",
            Self::Claude => "claude",
            Self::Codex => "codex",
            Self::Cursor => "agent",
            Self::Gemini => "gemini",
            Self::Copilot => "copilot",
            Self::Kilo => "kilo",
            Self::Pi => "pi",
            Self::Qwen => "qwen",
        }
    }

    /// When true, Curupira mints a UUID and passes it as `new_session_id`.
    #[must_use]
    pub const fn assigns_session_id(self) -> bool {
        matches!(self, Self::Copilot)
    }

    /// Documented native auto-model id, if any.
    #[must_use]
    pub const fn auto_model(self) -> Option<&'static str> {
        match self {
            Self::Cursor | Self::Gemini | Self::Copilot => Some("auto"),
            _ => None,
        }
    }
}

/// All built-in provider ids (stable order for docs/errors).
#[must_use]
pub fn known_providers() -> Vec<&'static str> {
    vec![
        "opencode", "claude", "codex", "cursor", "gemini", "copilot", "kilo", "pi", "qwen",
    ]
}

/// Inputs shared by headless and interactive launches.
#[derive(Debug, Clone)]
pub struct AgentRequest {
    pub message: String,
    pub cwd: PathBuf,
    pub session_id: Option<String>,
    pub new_session_id: Option<String>,
}

/// Headless argv ready for [`crate::process::run_process`].
#[derive(Debug, Clone)]
pub struct HeadlessLaunch {
    pub program: String,
    /// Full argv including `program` as argv[0] for display; process runner uses
    /// `program` + `args` (argv without program).
    pub args: Vec<String>,
    pub env: Vec<(String, String)>,
}

impl HeadlessLaunch {
    #[must_use]
    pub fn argv_display(&self) -> Vec<String> {
        let mut out = vec![self.program.clone()];
        out.extend(self.args.iter().cloned());
        out
    }
}

/// Optional interactive TUI launch (assistant panel).
#[derive(Debug, Clone)]
pub struct InteractiveLaunch {
    pub program: String,
    pub args: Vec<String>,
    pub env: Vec<(String, String)>,
    pub notes: Vec<String>,
}

/// Build a non-interactive coding-agent invocation.
pub fn build_headless(
    provider: AgentProvider,
    profile: &AgentProfile,
    request: &AgentRequest,
) -> Result<HeadlessLaunch, CurupiraError> {
    if profile.provider != provider.as_str() {
        return Err(CurupiraError::Dispatch(format!(
            "profile provider {:?} does not match {}",
            profile.provider,
            provider.as_str()
        )));
    }
    let args = match provider {
        AgentProvider::OpenCode => opencode::build_headless(profile, request)?,
        AgentProvider::Claude => claude::build_headless(profile, request)?,
        AgentProvider::Codex => codex::build_headless(profile, request)?,
        AgentProvider::Cursor => cursor::build_headless(profile, request)?,
        AgentProvider::Gemini => gemini::build_headless(profile, request)?,
        AgentProvider::Copilot => copilot::build_headless(profile, request)?,
        AgentProvider::Kilo => kilo::build_headless(profile, request)?,
        AgentProvider::Pi => pi::build_headless(profile, request)?,
        AgentProvider::Qwen => qwen::build_headless(profile, request)?,
    };
    Ok(HeadlessLaunch {
        program: provider.executable().into(),
        args,
        env: vec![],
    })
}

/// Build an interactive launch when the provider documents one; otherwise `None`.
pub fn build_interactive(
    provider: AgentProvider,
    profile: &AgentProfile,
    model: Option<&str>,
    prompt: Option<&str>,
) -> Result<Option<InteractiveLaunch>, CurupiraError> {
    if profile.provider != provider.as_str() {
        return Err(CurupiraError::Dispatch(format!(
            "profile provider {:?} does not match {}",
            profile.provider,
            provider.as_str()
        )));
    }
    let launch = match provider {
        AgentProvider::OpenCode => opencode::build_interactive(profile, model, prompt)?,
        AgentProvider::Claude => claude::build_interactive(profile, model, prompt)?,
        AgentProvider::Codex => codex::build_interactive(profile, model, prompt)?,
        AgentProvider::Cursor => cursor::build_interactive(profile, model, prompt)?,
        AgentProvider::Gemini => gemini::build_interactive(profile, model, prompt)?,
        AgentProvider::Copilot => copilot::build_interactive(profile, model, prompt)?,
        AgentProvider::Kilo => kilo::build_interactive(profile, model, prompt)?,
        AgentProvider::Pi => pi::build_interactive(profile, model, prompt)?,
        AgentProvider::Qwen => qwen::build_interactive(profile, model, prompt)?,
    };
    Ok(Some(launch))
}

/// Extract a native session id from one stdout line, if present.
#[must_use]
pub fn session_id_from_line(provider: AgentProvider, line: &str) -> Option<String> {
    match provider {
        AgentProvider::Pi => pi::session_id_from_line(line),
        AgentProvider::Gemini => gemini::session_id_from_line(line),
        _ => default_session_id_from_line(line),
    }
}

fn default_session_id_from_line(line: &str) -> Option<String> {
    let value: serde_json::Value = serde_json::from_str(line.trim()).ok()?;
    for key in ["sessionID", "session_id", "thread_id", "sessionId"] {
        if let Some(id) = value.get(key).and_then(|v| v.as_str()) {
            if !id.is_empty() {
                return Some(id.to_string());
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn profile(provider: &str, extra: serde_json::Map<String, serde_json::Value>) -> AgentProfile {
        AgentProfile {
            provider: provider.into(),
            extra,
        }
    }

    fn req(message: &str) -> AgentRequest {
        AgentRequest {
            message: message.into(),
            cwd: PathBuf::from("/tmp/work"),
            session_id: None,
            new_session_id: None,
        }
    }

    #[test]
    fn parse_all_known_providers() {
        for name in known_providers() {
            assert_eq!(AgentProvider::parse(name).unwrap().as_str(), name);
        }
        assert!(AgentProvider::parse("nope").is_err());
    }

    #[test]
    fn opencode_omits_optional_flags() {
        let launch = build_headless(
            AgentProvider::OpenCode,
            &profile("opencode", serde_json::Map::new()),
            &req("hello"),
        )
        .unwrap();
        assert_eq!(launch.program, "opencode");
        assert_eq!(launch.args, vec!["run", "--format", "json", "--", "hello"]);
    }

    #[test]
    fn opencode_includes_configured_flags() {
        let mut extra = serde_json::Map::new();
        extra.insert("model".into(), json!("p/m"));
        extra.insert("agent".into(), json!("build"));
        extra.insert("effort".into(), json!("high"));
        extra.insert("auto_approve".into(), json!(true));
        let launch = build_headless(
            AgentProvider::OpenCode,
            &profile("opencode", extra),
            &AgentRequest {
                message: "x".into(),
                cwd: PathBuf::from("."),
                session_id: Some("s1".into()),
                new_session_id: None,
            },
        )
        .unwrap();
        assert_eq!(
            launch.args,
            vec![
                "run",
                "--format",
                "json",
                "--session",
                "s1",
                "--model",
                "p/m",
                "--agent",
                "build",
                "--variant",
                "high",
                "--auto",
                "--",
                "x"
            ]
        );
    }

    #[test]
    fn claude_headless_baseline() {
        let launch = build_headless(
            AgentProvider::Claude,
            &profile("claude", serde_json::Map::new()),
            &req("fix"),
        )
        .unwrap();
        assert_eq!(
            launch.args,
            vec![
                "-p",
                "--output-format",
                "stream-json",
                "--verbose",
                "--",
                "fix"
            ]
        );
    }

    #[test]
    fn cursor_rejects_effort() {
        let mut extra = serde_json::Map::new();
        extra.insert("effort".into(), json!("high"));
        let err = build_headless(AgentProvider::Cursor, &profile("cursor", extra), &req("x"))
            .unwrap_err();
        assert!(err.to_string().contains("effort"));
    }

    #[test]
    fn copilot_requires_session() {
        let err = build_headless(
            AgentProvider::Copilot,
            &profile("copilot", serde_json::Map::new()),
            &req("x"),
        )
        .unwrap_err();
        assert!(err.to_string().contains("session"));
    }

    #[test]
    fn copilot_assigns_session_flags() {
        let launch = build_headless(
            AgentProvider::Copilot,
            &profile("copilot", serde_json::Map::new()),
            &AgentRequest {
                message: "-dash".into(),
                cwd: PathBuf::from("."),
                session_id: None,
                new_session_id: Some("uuid-1".into()),
            },
        )
        .unwrap();
        assert!(launch.args.iter().any(|a| a == "--no-ask-user"));
        assert!(launch.args.iter().any(|a| a == "--session-id=uuid-1"));
        assert!(launch.args.iter().any(|a| a == "--prompt=-dash"));
    }

    #[test]
    fn pi_approve_tri_state() {
        let mut extra = serde_json::Map::new();
        extra.insert("approve".into(), json!(false));
        let launch = build_headless(AgentProvider::Pi, &profile("pi", extra), &req("m")).unwrap();
        assert!(launch.args.iter().any(|a| a == "--no-approve"));
        assert!(!launch.args.iter().any(|a| a == "--approve"));
    }
}
