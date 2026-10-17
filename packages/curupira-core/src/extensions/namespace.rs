//! Map `[plugins.<alias>]` registrations to namespaced trigger types.

use std::collections::BTreeMap;

use crate::config::PluginConfiguration;
use crate::error::CurupiraError;
use crate::extensions::registry::ExtensionRegistry;

/// Resolved binding from a fully-qualified trigger type to an extension process.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TriggerBinding {
    /// TOML registration alias (`plugins-py`).
    pub alias: String,
    /// Local trigger name declared by the extension (`github-issues`).
    pub local_trigger: String,
    /// Fully-qualified automation trigger (`plugins-py/github-issues`).
    pub full_trigger: String,
    /// Extension registry name (`curupira-plugins`).
    pub extension_name: String,
    /// Launch settings from `[plugins.<alias>]` (`uvx` / `npx` + args).
    pub launch: PluginConfiguration,
}

/// Index of `alias/local` trigger types built from settings + installed manifests.
#[derive(Debug, Clone, Default)]
pub struct PluginNamespaceIndex {
    by_full: BTreeMap<String, TriggerBinding>,
}

impl PluginNamespaceIndex {
    /// Build the namespaced index from `[plugins.<alias>]` and installed extensions.
    pub fn build(
        plugins: &BTreeMap<String, PluginConfiguration>,
        registry: &ExtensionRegistry,
    ) -> Result<Self, CurupiraError> {
        let mut by_full: BTreeMap<String, TriggerBinding> = BTreeMap::new();
        for (alias, config) in plugins {
            let package = config.package();
            let extension = registry
                .iter()
                .find(|ext| {
                    ext.name == package
                        || ext
                            .manifest
                            .package
                            .as_ref()
                            .is_some_and(|pkg| pkg.name == package)
                })
                .ok_or_else(|| {
                    CurupiraError::Config(format!(
                        "plugins.{alias}: no installed extension matches package {package:?}"
                    ))
                })?;
            for local in &extension.manifest.trigger_types {
                if local.contains('/') {
                    return Err(CurupiraError::Plugin(format!(
                        "extension {:?}: trigger_types must be local names without '/'; got {local:?}",
                        extension.name
                    )));
                }
                let full = format!("{alias}/{local}");
                if let Some(other) = by_full.get(&full) {
                    return Err(CurupiraError::Config(format!(
                        "trigger_type {full:?} claimed by both {:?} and {:?}",
                        other.extension_name, extension.name
                    )));
                }
                by_full.insert(
                    full.clone(),
                    TriggerBinding {
                        alias: alias.clone(),
                        local_trigger: local.clone(),
                        full_trigger: full,
                        extension_name: extension.name.clone(),
                        launch: config.clone(),
                    },
                );
            }
        }
        Ok(Self { by_full })
    }

    #[must_use]
    pub fn resolve(&self, trigger_type: &str) -> Option<&TriggerBinding> {
        self.by_full.get(trigger_type)
    }

    pub fn iter(&self) -> impl Iterator<Item = &TriggerBinding> {
        self.by_full.values()
    }
}

/// Split `alias/local` or reject bare legacy names (except callers that handle `cron`).
pub fn parse_namespaced_trigger(trigger_type: &str) -> Result<(&str, &str), CurupiraError> {
    let Some((alias, local)) = trigger_type.split_once('/') else {
        return Err(CurupiraError::Config(format!(
            "trigger_type {trigger_type:?} must be namespaced as <plugins-alias>/<trigger> \
             (for example \"plugins-py/github-issues\")"
        )));
    };
    if alias.is_empty() || local.is_empty() || local.contains('/') {
        return Err(CurupiraError::Config(format!(
            "trigger_type {trigger_type:?} must be namespaced as <plugins-alias>/<trigger>"
        )));
    }
    Ok((alias, local))
}
