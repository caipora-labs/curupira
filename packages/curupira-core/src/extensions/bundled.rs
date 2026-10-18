//! Official extension manifests embedded in the binary for post-pip installs.

use crate::protocol::{ExtensionKind, ExtensionManifest, ExtensionRuntime, LaunchSpec, PackageRef};

use crate::version::VERSION;

/// Return manifests for official trigger extensions shipped with the wheel.
#[must_use]
pub fn official_manifests() -> Vec<ExtensionManifest> {
    let py = "python3".to_string();
    vec![ExtensionManifest {
        manifest_version: 1,
        name: "curupira-plugins".into(),
        version: VERSION.into(),
        protocol_version: 2,
        runtime: ExtensionRuntime::Python,
        kind: ExtensionKind::Trigger,
        launch: LaunchSpec::Executable {
            program: py,
            args: vec!["-m".into(), "curupira_plugins".into()],
        },
        package: Some(PackageRef {
            source: "bundled".into(),
            name: "curupira-plugins".into(),
            version: Some(VERSION.into()),
        }),
        capabilities: Default::default(),
        trigger_types: vec![
            "github-issues".into(),
            "github-pull-requests".into(),
            "github-project-items".into(),
        ],
        agent_providers: vec![],
    }]
}
