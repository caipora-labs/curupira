//! JSON-RPC method names and payload types for Curupira extensions.

use serde::de::{self, Deserializer, MapAccess, Visitor};
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
    pub error: Option<super::RpcError>,
}

/// Method: negotiate protocol version and identify the extension.
pub const METHOD_INITIALIZE: &str = "initialize";
/// Method: list triggers contributed by this process.
pub const METHOD_DESCRIBE: &str = "describe";
/// Method: return JSON Schema (draft 2020-12) for a trigger's automation table.
pub const METHOD_TRIGGER_SCHEMA: &str = "trigger/schema";
/// Method: validate an automation configuration object.
pub const METHOD_TRIGGER_VALIDATE: &str = "trigger/validate";
/// Method: discover the next result (poll). Returns one key/value list or null.
pub const METHOD_TRIGGER_POLL: &str = "trigger/poll";
/// Method: lifecycle — coding agent about to start.
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

/// One string pair from a trigger result. The protocol assigns no meaning to either side.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct KeyValue {
    pub key: String,
    pub value: String,
}

/// `trigger/poll` success payload.
///
/// `values: null` means no item was found. An empty list is an item with no pairs.
/// A filled list is the item. The field is required: omitting it is a protocol error.
///
/// `Option` would otherwise accept a missing field as `None`. The manual
/// deserializer keeps that case distinct from JSON `null`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct TriggerPollResult {
    pub values: Option<Vec<KeyValue>>,
}

impl<'de> Deserialize<'de> for TriggerPollResult {
    fn deserialize<D: Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        struct ResultVisitor;

        impl<'de> Visitor<'de> for ResultVisitor {
            type Value = TriggerPollResult;

            fn expecting(&self, formatter: &mut std::fmt::Formatter) -> std::fmt::Result {
                formatter.write_str("an object with a values field")
            }

            fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<Self::Value, A::Error> {
                let mut values = None;
                while let Some(key) = map.next_key::<String>()? {
                    if key != "values" {
                        return Err(de::Error::unknown_field(&key, &["values"]));
                    }
                    if values.is_some() {
                        return Err(de::Error::duplicate_field("values"));
                    }
                    values = Some(map.next_value::<Option<Vec<KeyValue>>>()?);
                }
                Ok(TriggerPollResult {
                    values: values.ok_or_else(|| de::Error::missing_field("values"))?,
                })
            }
        }

        deserializer.deserialize_struct("TriggerPollResult", &["values"], ResultVisitor)
    }
}

/// Lifecycle payload. Carries the trigger result only, not host execution state.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct TriggerLifecycleParams {
    pub trigger_type: String,
    pub values: Vec<KeyValue>,
}

#[cfg(test)]
mod tests {
    use serde_json::json;

    use super::{KeyValue, TriggerPollResult};

    #[test]
    fn poll_result_null_means_no_item() {
        let parsed: TriggerPollResult = serde_json::from_value(json!({"values": null})).unwrap();
        assert!(parsed.values.is_none());
    }

    #[test]
    fn poll_result_empty_list_is_an_item() {
        let parsed: TriggerPollResult = serde_json::from_value(json!({"values": []})).unwrap();
        assert_eq!(parsed.values, Some(vec![]));
    }

    #[test]
    fn poll_result_accepts_string_pairs() {
        let parsed: TriggerPollResult = serde_json::from_value(json!({
            "values": [{"key": "issue-number", "value": "42"}]
        }))
        .unwrap();
        assert_eq!(
            parsed.values.unwrap(),
            vec![KeyValue {
                key: "issue-number".into(),
                value: "42".into(),
            }]
        );
    }

    #[test]
    fn poll_result_rejects_missing_values() {
        assert!(serde_json::from_value::<TriggerPollResult>(json!({})).is_err());
    }

    #[test]
    fn poll_result_rejects_legacy_task_object() {
        let legacy = json!({"task": {"id": "1", "title": "t", "url": "u", "item": {}}});
        assert!(serde_json::from_value::<TriggerPollResult>(legacy).is_err());
    }

    #[test]
    fn poll_result_rejects_non_string_pair() {
        let parsed = serde_json::from_value::<TriggerPollResult>(json!({
            "values": [{"key": "n", "value": 1}]
        }));
        assert!(parsed.is_err());
    }

    #[test]
    fn poll_result_rejects_unknown_pair_field() {
        let parsed = serde_json::from_value::<TriggerPollResult>(json!({
            "values": [{"key": "n", "value": "1", "id": "1"}]
        }));
        assert!(parsed.is_err());
    }

    #[test]
    fn shared_fixtures_round_trip() {
        for raw in [
            include_str!("../../tests/fixtures/protocol/poll-values.json"),
            include_str!("../../tests/fixtures/protocol/poll-null.json"),
            include_str!("../../tests/fixtures/protocol/poll-empty.json"),
        ] {
            let parsed: TriggerPollResult = serde_json::from_str(raw).unwrap();
            let again = serde_json::to_value(&parsed).unwrap();
            let original: serde_json::Value = serde_json::from_str(raw).unwrap();
            assert_eq!(again, original);
        }
        let parsed: TriggerPollResult = serde_json::from_str(include_str!(
            "../../tests/fixtures/protocol/poll-values.json"
        ))
        .unwrap();
        let values = parsed.values.unwrap();
        assert_eq!(values[0].key, "issue-number");
        assert_eq!(values[0].value, "42");
        assert!(values
            .iter()
            .any(|pair| pair.key == "ready" && pair.value == "true"));
        assert!(values
            .iter()
            .any(|pair| pair.key == "note" && pair.value == "null"));
        assert!(!values.iter().any(|pair| {
            matches!(
                pair.key.as_str(),
                "id" | "title" | "url" | "number" | "item"
            )
        }));
    }
}
