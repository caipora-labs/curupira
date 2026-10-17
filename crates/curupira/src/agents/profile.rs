//! Helpers for reading flattened TOML profile extras.

use crate::config::AgentProfile;
use crate::error::CurupiraError;

/// Optional string field from profile extras.
pub fn opt_str(profile: &AgentProfile, key: &str) -> Result<Option<String>, CurupiraError> {
    match profile.extra.get(key) {
        None | Some(serde_json::Value::Null) => Ok(None),
        Some(serde_json::Value::String(s)) => {
            if s.is_empty() {
                Err(CurupiraError::Config(format!(
                    "profile field {key:?} must be a non-empty string"
                )))
            } else {
                Ok(Some(s.clone()))
            }
        }
        Some(other) => Err(CurupiraError::Config(format!(
            "profile field {key:?} must be a string, got {other}"
        ))),
    }
}

/// Boolean field; missing defaults to `false` unless `default` is provided.
pub fn bool_extra(profile: &AgentProfile, key: &str, default: bool) -> Result<bool, CurupiraError> {
    match profile.extra.get(key) {
        None | Some(serde_json::Value::Null) => Ok(default),
        Some(serde_json::Value::Bool(b)) => Ok(*b),
        Some(other) => Err(CurupiraError::Config(format!(
            "profile field {key:?} must be a boolean, got {other}"
        ))),
    }
}

/// Optional boolean that preserves three-state semantics (`None` / `Some(true)` / `Some(false)`).
pub fn opt_bool(profile: &AgentProfile, key: &str) -> Result<Option<bool>, CurupiraError> {
    match profile.extra.get(key) {
        None | Some(serde_json::Value::Null) => Ok(None),
        Some(serde_json::Value::Bool(b)) => Ok(Some(*b)),
        Some(other) => Err(CurupiraError::Config(format!(
            "profile field {key:?} must be a boolean, got {other}"
        ))),
    }
}

/// String list from a JSON array of strings.
pub fn string_list(profile: &AgentProfile, key: &str) -> Result<Vec<String>, CurupiraError> {
    match profile.extra.get(key) {
        None | Some(serde_json::Value::Null) => Ok(vec![]),
        Some(serde_json::Value::Array(items)) => {
            let mut out = Vec::with_capacity(items.len());
            for item in items {
                let Some(s) = item.as_str() else {
                    return Err(CurupiraError::Config(format!(
                        "profile field {key:?} entries must be strings"
                    )));
                };
                if s.is_empty() {
                    return Err(CurupiraError::Config(format!(
                        "profile field {key:?} entries must be non-empty"
                    )));
                }
                out.push(s.to_string());
            }
            Ok(out)
        }
        Some(other) => Err(CurupiraError::Config(format!(
            "profile field {key:?} must be an array of strings, got {other}"
        ))),
    }
}

/// Optional positive integer (≥ 1).
pub fn opt_u64(profile: &AgentProfile, key: &str) -> Result<Option<u64>, CurupiraError> {
    match profile.extra.get(key) {
        None | Some(serde_json::Value::Null) => Ok(None),
        Some(serde_json::Value::Number(n)) => {
            let Some(v) = n.as_u64() else {
                return Err(CurupiraError::Config(format!(
                    "profile field {key:?} must be a positive integer"
                )));
            };
            if v < 1 {
                return Err(CurupiraError::Config(format!(
                    "profile field {key:?} must be >= 1"
                )));
            }
            Ok(Some(v))
        }
        Some(other) => Err(CurupiraError::Config(format!(
            "profile field {key:?} must be an integer, got {other}"
        ))),
    }
}

/// Reject unsupported keys that older docs map to hard errors.
pub fn reject_keys(
    profile: &AgentProfile,
    keys: &[&str],
    reason: &str,
) -> Result<(), CurupiraError> {
    for key in keys {
        if profile.extra.contains_key(*key) {
            return Err(CurupiraError::Config(format!(
                "{reason}: unsupported profile field {key:?}"
            )));
        }
    }
    Ok(())
}
