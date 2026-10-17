//! Official extension manifests embedded in the binary for post-pip installs.

use curupira_protocol::{
    ExtensionKind, ExtensionManifest, ExtensionRuntime, LaunchSpec, PackageRef,
};

use crate::version::VERSION;

/// Return manifests for official extensions shipped with the wheel.
#[must_use]
pub fn official_manifests() -> Vec<ExtensionManifest> {
    let py = "python3".to_string();
    vec![
        ExtensionManifest {
            manifest_version: 1,
            name: "curupira-github".into(),
            version: VERSION.into(),
            protocol_version: 1,
            runtime: ExtensionRuntime::Python,
            kind: ExtensionKind::Trigger,
            launch: LaunchSpec::Executable {
                program: py.clone(),
                args: vec!["-m".into(), "curupira_official.github_ext".into()],
            },
            package: Some(PackageRef {
                source: "bundled".into(),
                name: "curupira".into(),
                version: Some(VERSION.into()),
            }),
            capabilities: Default::default(),
            trigger_types: vec!["github-issues".into(), "github-pull-requests".into()],
            agent_providers: vec![],
        },
        ExtensionManifest {
            manifest_version: 1,
            name: "curupira-azure".into(),
            version: VERSION.into(),
            protocol_version: 1,
            runtime: ExtensionRuntime::Python,
            kind: ExtensionKind::Trigger,
            launch: LaunchSpec::Executable {
                program: py.clone(),
                args: vec!["-m".into(), "curupira_official.azure_ext".into()],
            },
            package: Some(PackageRef {
                source: "bundled".into(),
                name: "curupira".into(),
                version: Some(VERSION.into()),
            }),
            capabilities: Default::default(),
            trigger_types: vec!["azure-cli-pull-requests".into()],
            agent_providers: vec![],
        },
        ExtensionManifest {
            manifest_version: 1,
            name: "curupira-trello".into(),
            version: VERSION.into(),
            protocol_version: 1,
            runtime: ExtensionRuntime::Python,
            kind: ExtensionKind::Trigger,
            launch: LaunchSpec::Executable {
                program: py.clone(),
                args: vec!["-m".into(), "curupira_official.trello_ext".into()],
            },
            package: Some(PackageRef {
                source: "bundled".into(),
                name: "curupira".into(),
                version: Some(VERSION.into()),
            }),
            capabilities: Default::default(),
            trigger_types: vec!["trello-cli-cards".into()],
            agent_providers: vec![],
        },
        ExtensionManifest {
            manifest_version: 1,
            name: "curupira-monday".into(),
            version: VERSION.into(),
            protocol_version: 1,
            runtime: ExtensionRuntime::Python,
            kind: ExtensionKind::Trigger,
            launch: LaunchSpec::Executable {
                program: py.clone(),
                args: vec!["-m".into(), "curupira_official.monday_ext".into()],
            },
            package: Some(PackageRef {
                source: "bundled".into(),
                name: "curupira".into(),
                version: Some(VERSION.into()),
            }),
            capabilities: Default::default(),
            trigger_types: vec!["monday-items".into()],
            agent_providers: vec![],
        },
        ExtensionManifest {
            manifest_version: 1,
            name: "curupira-agents".into(),
            version: VERSION.into(),
            protocol_version: 1,
            runtime: ExtensionRuntime::Python,
            kind: ExtensionKind::Agent,
            launch: LaunchSpec::Executable {
                program: py,
                args: vec!["-m".into(), "curupira_official.agents_ext".into()],
            },
            package: Some(PackageRef {
                source: "bundled".into(),
                name: "curupira".into(),
                version: Some(VERSION.into()),
            }),
            capabilities: Default::default(),
            trigger_types: vec![],
            agent_providers: vec![
                "opencode".into(),
                "claude".into(),
                "codex".into(),
                "cursor".into(),
                "gemini".into(),
                "copilot".into(),
                "kilo".into(),
                "pi".into(),
                "qwen".into(),
            ],
        },
    ]
}
