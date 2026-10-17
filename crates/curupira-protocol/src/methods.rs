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
/// Method: list triggers contributed by this process.
pub const METHOD_DESCRIBE: &str = "describe";
/// Method: return JSON Schema (draft 2020-12) for a trigger's automation table.
pub const METHOD_TRIGGER_SCHEMA: &str = "trigger/schema";
/// Method: validate an automation configuration object.
pub const METHOD_TRIGGER_VALIDATE: &str = "trigger/validate";
/// Method: discover currently available tasks (poll).
pub const METHOD_TRIGGER_POLL: &str = "trigger/poll";
/// Method: lifecycle — task about to start coding agent.
pub const METHOD_TRIGGER_ON_STARTED: &str = "trigger/onStarted";
/// Method: lifecycle — coding agent finished.
pub const METHOD_TRIGGER_ON_FINISHED: &str = "trigger/onFinished";
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
    /// Always empty for current hosts; retained so older extension processes that
    /// still emit `"agents": []` deserialize cleanly.
    #[serde(default)]
    pub agents: Vec<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TriggerDescription {
    pub trigger_type: String,
    #[serde(default)]
    pub prompt_fields: Vec<String>,
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
    pub tasks: Vec<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TriggerLifecycleParams {
    pub trigger_type: String,
    pub task: Value,
}
