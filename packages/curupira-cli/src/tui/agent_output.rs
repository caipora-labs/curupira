//! Turns coding-agent stdout lines into history entries.
//!
//! Agents in JSON mode print one event per line: OpenCode 2.x (`text`, `tool_use`, `error`)
//! and Claude stream-json (`assistant` messages with `text` and `tool_use` blocks). Plain-text
//! agents print prose. Bookkeeping events (step start/finish, usage, results that repeat the
//! last text) produce nothing.

use serde_json::Value;

use super::app::Entry;

/// Entries for one stdout line from `agent`.
#[must_use]
pub fn entries(line: &str, agent: &str) -> Vec<Entry> {
    let line = line.trim();
    if line.is_empty() {
        return Vec::new();
    }
    let Ok(event) = serde_json::from_str::<Value>(line) else {
        return vec![agent_text(agent, line)];
    };
    if let Some(error) = event.get("error") {
        let message = error
            .get("message")
            .and_then(Value::as_str)
            .or_else(|| error.as_str())
            .unwrap_or("unknown error");
        return vec![Entry::Error(message.to_owned())];
    }
    let part = event.get("part");
    match event.get("type").and_then(Value::as_str) {
        Some("text") => part
            .and_then(|p| p.get("text"))
            .and_then(Value::as_str)
            .map(|text| vec![agent_text(agent, text)])
            .unwrap_or_default(),
        Some("tool_use") => part.map(opencode_tool).into_iter().collect(),
        Some("assistant") => event
            .pointer("/message/content")
            .and_then(Value::as_array)
            .map(|blocks| {
                blocks
                    .iter()
                    .filter_map(|b| claude_block(b, agent))
                    .collect()
            })
            .unwrap_or_default(),
        _ => Vec::new(),
    }
}

fn agent_text(agent: &str, text: &str) -> Entry {
    Entry::Agent {
        name: agent.to_owned(),
        text: text.trim().to_owned(),
    }
}

fn opencode_tool(part: &Value) -> Entry {
    let name = part.get("tool").and_then(Value::as_str).unwrap_or("tool");
    let state = part.get("state");
    let detail = state
        .and_then(|s| s.get("title"))
        .and_then(Value::as_str)
        .or_else(|| {
            state
                .and_then(|s| s.pointer("/input/command"))
                .and_then(Value::as_str)
        })
        .or_else(|| {
            state
                .and_then(|s| s.pointer("/input/description"))
                .and_then(Value::as_str)
        })
        .unwrap_or_default();
    Entry::Tool {
        name: name.to_owned(),
        detail: first_line(detail),
    }
}

fn claude_block(block: &Value, agent: &str) -> Option<Entry> {
    match block.get("type").and_then(Value::as_str)? {
        "text" => block
            .get("text")
            .and_then(Value::as_str)
            .filter(|t| !t.trim().is_empty())
            .map(|t| agent_text(agent, t)),
        "tool_use" => {
            let input = block.get("input");
            let detail = ["command", "description", "file_path", "pattern"]
                .iter()
                .find_map(|key| input.and_then(|i| i.get(key)).and_then(Value::as_str))
                .unwrap_or_default();
            Some(Entry::Tool {
                name: block
                    .get("name")
                    .and_then(Value::as_str)
                    .unwrap_or("tool")
                    .to_owned(),
                detail: first_line(detail),
            })
        }
        _ => None,
    }
}

fn first_line(text: &str) -> String {
    text.lines().next().unwrap_or_default().trim().to_owned()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn opencode_events() {
        let text = r#"{"type":"text","part":{"type":"text","text":"Merged.\n"}}"#;
        assert_eq!(
            entries(text, "opencode"),
            vec![agent_text("opencode", "Merged.")]
        );

        let tool = r#"{"type":"tool_use","part":{"tool":"shell","state":{"status":"completed","input":{"command":"gh pr checks 223\nmore"}}}}"#;
        assert_eq!(
            entries(tool, "opencode"),
            vec![Entry::Tool {
                name: "shell".into(),
                detail: "gh pr checks 223".into()
            }]
        );

        let error = r#"{"type":"error","error":{"type":"provider.no-route","message":"Model unavailable: x"}}"#;
        assert_eq!(
            entries(error, "opencode"),
            vec![Entry::Error("Model unavailable: x".into())]
        );

        assert!(entries(r#"{"type":"step_start","part":{}}"#, "opencode").is_empty());
    }

    #[test]
    fn claude_stream_json() {
        let line = r#"{"type":"assistant","message":{"content":[{"type":"text","text":"Checking CI"},{"type":"tool_use","name":"Bash","input":{"command":"gh pr checks 1"}}]}}"#;
        assert_eq!(
            entries(line, "claude"),
            vec![
                agent_text("claude", "Checking CI"),
                Entry::Tool {
                    name: "Bash".into(),
                    detail: "gh pr checks 1".into()
                }
            ]
        );
        assert!(entries(r#"{"type":"result","result":"done"}"#, "claude").is_empty());
    }

    #[test]
    fn plain_text_and_blank_lines() {
        assert_eq!(
            entries("  working on it ", "codex"),
            vec![agent_text("codex", "working on it")]
        );
        assert!(entries("   ", "codex").is_empty());
    }
}
