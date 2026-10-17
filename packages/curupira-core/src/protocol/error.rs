//! Structured protocol and RPC errors.

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// JSON-RPC / Curupira error codes.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(transparent)]
pub struct ErrorCode(pub i64);

impl ErrorCode {
    pub const PARSE_ERROR: Self = Self(-32700);
    pub const INVALID_REQUEST: Self = Self(-32600);
    pub const METHOD_NOT_FOUND: Self = Self(-32601);
    pub const INVALID_PARAMS: Self = Self(-32602);
    pub const INTERNAL_ERROR: Self = Self(-32603);
    /// Transport failed (EOF, broken pipe, spawn failure).
    pub const TRANSPORT: Self = Self(-32000);
    /// Protocol framing or version negotiation failed.
    pub const PROTOCOL: Self = Self(-32001);
    /// Extension command / trigger / agent execution failed.
    pub const EXECUTION: Self = Self(-32002);
    /// Configuration validation failed inside the extension.
    pub const CONFIG: Self = Self(-32003);
    /// Timeout waiting for an extension response.
    pub const TIMEOUT: Self = Self(-32004);
}

/// JSON-RPC 2.0 error object.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct RpcError {
    pub code: ErrorCode,
    pub message: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub data: Option<serde_json::Value>,
}

impl RpcError {
    #[must_use]
    pub fn new(code: ErrorCode, message: impl Into<String>) -> Self {
        Self {
            code,
            message: message.into(),
            data: None,
        }
    }
}

/// Host-side protocol failures distinct from extension execution errors.
#[derive(Debug, Error)]
pub enum ProtocolError {
    #[error("transport error: {0}")]
    Transport(String),
    #[error("protocol error: {0}")]
    Protocol(String),
    #[error("execution error: {0}")]
    Execution(String),
    #[error("timeout: {0}")]
    Timeout(String),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
}
