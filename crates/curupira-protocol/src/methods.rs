//! JSON-RPC method names and payload types for Curupira extensions.

use serde::{Deserialize, Serialize};
use serde_json::Value;

/// JSON-RPC 2.0 request envelope.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Request {
    pub jsonrpc: String,
    pub id: Value,
    pub method: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub params: Option<Value>,
}

impl Request {
    #[must_use]
    pub fn new(id: impl Into<Value>, method: impl Into<String>, params: Option<Value>) -> Self {
        Self {
            jsonrpc: "2.0".into(),
            id: id.into(),
            method: method.into(),
            params,
        }
    }
}

/// JSON-RPC 2.0 response envelope.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Response {
    pub jsonrpc: String,
    pub id: Value,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub result: Option<Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<crate::RpcError>,
}

/// Method: negotiate protocol version and identify the extension.
pub const METHOD_INITIALIZE: &str = "initialize";
/// Method: list triggers and agents contributed by this process.
pub const METHOD_DESCRIBE: &str = "describe";
/// Method: return JSON Schema (draft 2020-12) for a trigger's automation table.
pub const METHOD_TRIGGER_SCHEMA: &str = "trigger/schema";
/// Method: validate an automation configuration object.
pub const METHOD_TRIGGER_VALIDATE: &str = "trigger/validate";
/// Method: discover the next available task (poll). Returns at most one item.
pub const METHOD_TRIGGER_POLL: &str = "trigger/poll";
/// Method: lifecycle — task about to start coding agent.
pub const METHOD_TRIGGER_ON_STARTED: &str = "trigger/onStarted";
/// Method: lifecycle — coding agent finished.
pub const METHOD_TRIGGER_ON_FINISHED: &str = "trigger/onFinished";
/// Method: build argv for a coding-agent CLI.
pub const METHOD_AGENT_BUILD_ARGUMENTS: &str = "agent/buildArguments";
/// Method: optional interactive launch spec for the TUI assistant.
pub const METHOD_AGENT_INTERACTIVE_LAUNCH: &str = "agent/interactiveLaunch";
/// Method: graceful shutdown.
pub const METHOD_SHUTDOWN: &str = "shutdown";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InitializeParams {
    pub protocol_version: u32,
    #[serde(default)]
    pub client_info: ClientInfo,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ClientInfo {
    pub name: String,
    pub version: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InitializeResult {
    pub protocol_version: u32,
    pub server_info: ServerInfo,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerInfo {
    pub name: String,
    pub version: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DescribeResult {
    pub triggers: Vec<TriggerDescription>,
    pub agents: Vec<AgentDescription>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TriggerDescription {
    pub trigger_type: String,
    #[serde(default)]
    pub prompt_fields: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentDescription {
    pub provider: String,
    pub executable: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TriggerSchemaParams {
    pub trigger_type: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TriggerSchemaResult {
    /// JSON Schema object for the automation table (excluding shared core fields optional).
    pub schema: Value,
    pub prompt_fields: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TriggerValidateParams {
    pub trigger_type: String,
    pub configuration: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TriggerValidateResult {
    pub ok: bool,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub configuration: Option<Value>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TriggerPollParams {
    pub trigger_type: String,
    pub automation: Value,
    pub preview: bool,
    #[serde(default)]
    pub limit: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TriggerPollResult {
    /// Next task payload, or `null` when no item is available this call.
    #[serde(default, deserialize_with = "deserialize_optional_task")]
    pub task: Option<Value>,
}

fn deserialize_optional_task<'de, D>(deserializer: D) -> Result<Option<Value>, D::Error>
where
    D: serde::Deserializer<'de>,
{
    let value = Option::<Value>::deserialize(deserializer)?;
    match value {
        None | Some(Value::Null) => Ok(None),
        Some(other) => Ok(Some(other)),
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TriggerLifecycleParams {
    pub trigger_type: String,
    pub task: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentBuildArgumentsParams {
    pub provider: String,
    pub profile: Value,
    pub request: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentBuildArgumentsResult {
    pub argv: Vec<String>,
    #[serde(default)]
    pub env: Vec<(String, String)>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentInteractiveLaunchParams {
    pub provider: String,
    pub profile: Value,
    pub model: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentInteractiveLaunchResult {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub spec: Option<InteractiveLaunchSpec>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InteractiveLaunchSpec {
    pub program: String,
    pub args: Vec<String>,
    #[serde(default)]
    pub env: Vec<(String, String)>,
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::TriggerPollResult;

    #[test]
    fn poll_result_accepts_null_task() {
        let parsed: TriggerPollResult = serde_json::from_value(json!({"task": null})).unwrap();
        assert!(parsed.task.is_none());
    }

    #[test]
    fn poll_result_accepts_missing_task_as_none() {
        let parsed: TriggerPollResult = serde_json::from_value(json!({})).unwrap();
        assert!(parsed.task.is_none());
    }

    #[test]
    fn poll_result_accepts_object_task() {
        let parsed: TriggerPollResult =
            serde_json::from_value(json!({"task": {"id": "1", "title": "t"}})).unwrap();
        assert_eq!(parsed.task.unwrap()["id"], "1");
    }
}
