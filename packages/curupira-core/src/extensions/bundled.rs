//! Official extension manifests embedded in the binary for post-pip installs.

use crate::protocol::{ExtensionKind, ExtensionManifest, ExtensionRuntime, LaunchSpec, PackageRef};

use crate::version::VERSION;

/// Return manifests for official trigger extensions shipped with the wheel.
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
                args: vec!["-m".into(), "curupira_github".into()],
            },
            package: Some(PackageRef {
                source: "bundled".into(),
                name: "curupira-github".into(),
                version: Some(VERSION.into()),
            }),
            capabilities: Default::default(),
            trigger_types: vec!["github_issues".into(), "github_pull_requests".into()],
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
                args: vec!["-m".into(), "curupira_azure".into()],
            },
            package: Some(PackageRef {
                source: "bundled".into(),
                name: "curupira-azure".into(),
                version: Some(VERSION.into()),
            }),
            capabilities: Default::default(),
            trigger_types: vec!["azure_cli_pull_requests".into()],
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
                args: vec!["-m".into(), "curupira_trello".into()],
            },
            package: Some(PackageRef {
                source: "bundled".into(),
                name: "curupira-trello".into(),
                version: Some(VERSION.into()),
            }),
            capabilities: Default::default(),
            trigger_types: vec!["trello_cli_cards".into()],
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
                program: py,
                args: vec!["-m".into(), "curupira_monday".into()],
            },
            package: Some(PackageRef {
                source: "bundled".into(),
                name: "curupira-monday".into(),
                version: Some(VERSION.into()),
            }),
            capabilities: Default::default(),
            trigger_types: vec!["monday_items".into()],
            agent_providers: vec![],
        },
    ]
}
