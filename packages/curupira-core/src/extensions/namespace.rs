//! Map `[plugins.<alias>]` registrations to namespaced trigger types.

use std::collections::BTreeMap;

use crate::config::PluginConfiguration;
use crate::error::CurupiraError;
use crate::extensions::host::ExtensionHost;
use crate::extensions::tools::tool_allowed;

/// Resolved binding from a fully-qualified trigger type to an extension process.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TriggerBinding {
    /// TOML registration alias (`plugins-py`).
    pub alias: String,
    /// Local trigger name declared by the extension (`github-issues`).
    pub local_trigger: String,
    /// Fully-qualified automation trigger (`plugins-py/github-issues`).
    pub full_trigger: String,
    /// Launch settings from `[plugins.<alias>]` (`uvx` / `npx` + args).
    pub launch: PluginConfiguration,
}

/// Index of `alias/local` trigger types built from settings + live `describe`.
#[derive(Debug, Clone, Default)]
pub struct PluginNamespaceIndex {
    by_full: BTreeMap<String, TriggerBinding>,
}

impl PluginNamespaceIndex {
    /// Build the namespaced index by spawning each registered plugin and calling `describe`.
    ///
    /// `env_vars` are the `[environment.vars]` overwrites applied to each plugin process.
    pub fn build(
        plugins: &BTreeMap<String, PluginConfiguration>,
        env_vars: &BTreeMap<String, String>,
    ) -> Result<Self, CurupiraError> {
        let mut by_full: BTreeMap<String, TriggerBinding> = BTreeMap::new();
        for (alias, config) in plugins {
            let mut host = ExtensionHost::spawn_plugin(alias, config, env_vars)?;
            let described = host.describe().map_err(|err| {
                CurupiraError::Config(format!("plugins.{alias}: describe failed: {err}"))
            })?;
            let _ = host.shutdown();

            if described.triggers.is_empty() {
                return Err(CurupiraError::Config(format!(
                    "plugins.{alias}: extension describe returned no triggers"
                )));
            }

            let mut matched = 0_usize;
            for trigger in described.triggers {
                let local = trigger.trigger_type;
                if local.contains('/') {
                    return Err(CurupiraError::Config(format!(
                        "plugins.{alias}: trigger names must be local (no '/'); got {local:?}"
                    )));
                }
                if !tool_allowed(&local, &config.tools) {
                    continue;
                }
                matched += 1;
                let full = format!("{alias}/{local}");
                if let Some(other) = by_full.get(&full) {
                    return Err(CurupiraError::Config(format!(
                        "trigger_type {full:?} claimed by both {:?} and {alias:?}",
                        other.alias
                    )));
                }
                by_full.insert(
                    full.clone(),
                    TriggerBinding {
                        alias: alias.clone(),
                        local_trigger: local,
                        full_trigger: full,
                        launch: config.clone(),
                    },
                );
            }
            if matched == 0 {
                return Err(CurupiraError::Config(format!(
                    "plugins.{alias}: tools filter matched no triggers (tools = {:?})",
                    config.tools
                )));
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
