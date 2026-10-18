//! Extension manifest on disk (TOML). Discovery never executes extension code.

use serde::{Deserialize, Serialize};

/// Canonical manifest file name inside an installed extension directory.
pub const MANIFEST_FILE_NAME: &str = "curupira-extension.toml";

/// How the host launches the extension process.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ExtensionRuntime {
    Python,
    Node,
    /// Absolute or PATH-resolved executable (tests and local tools).
    Executable,
}

/// Whether the extension contributes triggers (task sources).
///
/// Coding agents are built into the Rust core; `agent` / `both` remain only so
/// older on-disk manifests deserialize and can be rejected cleanly.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum ExtensionKind {
    Trigger,
    Agent,
    Both,
}

/// Declared capability strings (informational; not a sandbox).
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExtensionCapability {
    #[serde(default)]
    pub permissions: Vec<String>,
}

/// Versioned extension manifest.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct ExtensionManifest {
    /// Manifest format version (independent of the wire protocol).
    pub manifest_version: u32,
    /// Unique extension name (`^[a-z0-9][a-z0-9_-]*$`).
    pub name: String,
    /// Extension package version (semver-like string).
    pub version: String,
    /// Wire protocol version this extension implements.
    pub protocol_version: u32,
    pub runtime: ExtensionRuntime,
    pub kind: ExtensionKind,
    /// Launch specification resolved by the host.
    pub launch: LaunchSpec,
    /// Optional installed package coordinates.
    #[serde(default)]
    pub package: Option<PackageRef>,
    #[serde(default)]
    pub capabilities: ExtensionCapability,
    /// Local trigger types contributed (`github-issues`, …).
    /// Settings address them as `<plugins-alias>/<local>` after `[plugins.<alias>]`.
    #[serde(default)]
    pub trigger_types: Vec<String>,
    /// Deprecated: coding agents are built into the core. Ignored when non-empty
    /// except that agent-only manifests fail validation.
    #[serde(default)]
    pub agent_providers: Vec<String>,
}

/// How to start the extension process (argv only; never a shell string).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum LaunchSpec {
    /// `uvx --from package==ver executable` (or managed env equivalent).
    Uvx {
        package: String,
        version: Option<String>,
        executable: String,
        #[serde(default)]
        args: Vec<String>,
    },
    /// `npx --yes package@version` (+ optional bin).
    Npx {
        package: String,
        version: Option<String>,
        #[serde(default)]
        bin: Option<String>,
        #[serde(default)]
        args: Vec<String>,
    },
    /// Direct executable + args (local / test / PATH).
    Executable {
        program: String,
        #[serde(default)]
        args: Vec<String>,
    },
}

/// Installed distribution metadata for display.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PackageRef {
    pub source: String,
    pub name: String,
    #[serde(default)]
    pub version: Option<String>,
}

impl ExtensionManifest {
    /// Parse a TOML manifest document.
    pub fn from_toml_str(text: &str) -> Result<Self, toml::de::Error> {
        toml::from_str(text)
    }

    /// Serialize to TOML.
    pub fn to_toml_string(&self) -> Result<String, toml::ser::Error> {
        toml::to_string_pretty(self)
    }

    /// Basic structural validation without launching the extension.
    pub fn validate(&self) -> Result<(), String> {
        if self.manifest_version != 1 {
            return Err(format!(
                "unsupported manifest_version {}",
                self.manifest_version
            ));
        }
        if self.name.is_empty()
            || !self
                .name
                .chars()
                .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_')
        {
            return Err("invalid extension name".into());
        }
        if self.trigger_types.is_empty() {
            return Err(
                "manifest must declare trigger_types (coding agents are built into Curupira)"
                    .into(),
            );
        }
        if matches!(self.kind, ExtensionKind::Agent) || !self.agent_providers.is_empty() {
            return Err(
                "coding-agent extensions are no longer supported; agents are built into the Rust core"
                    .into(),
            );
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_minimal() {
        let text = r#"
manifest_version = 1
name = "curupira-plugins"
version = "0.2.0"
protocol_version = 2
runtime = "python"
kind = "trigger"
trigger_types = ["github-issues", "github-pull-requests"]

[launch]
type = "executable"
program = "python3"
args = ["-m", "curupira_plugins"]
"#;
        let m = ExtensionManifest::from_toml_str(text).unwrap();
        m.validate().unwrap();
        assert_eq!(m.name, "curupira-plugins");
    }
}
