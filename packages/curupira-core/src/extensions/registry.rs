//! On-disk extension registry. Listing never executes extension code.

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use crate::protocol::{ExtensionManifest, MANIFEST_FILE_NAME};

use crate::agents::{known_providers, AgentProvider};
use crate::error::CurupiraError;
use crate::runtime::extensions_dir;
use crate::version::VERSION;

/// One installed extension (manifest only).
#[derive(Debug, Clone)]
pub struct InstalledExtension {
    pub name: String,
    pub dir: PathBuf,
    pub manifest: ExtensionManifest,
}

/// Deterministic registry loaded from `~/.curupira/extensions/<name>/`.
#[derive(Debug, Clone, Default)]
pub struct ExtensionRegistry {
    by_name: BTreeMap<String, InstalledExtension>,
    trigger_index: BTreeMap<String, String>,
}

impl ExtensionRegistry {
    #[must_use]
    pub fn empty() -> Self {
        Self::default()
    }

    /// Load manifests from managed + bundled directories without spawning processes.
    pub fn load() -> Result<Self, CurupiraError> {
        let mut reg = Self::empty();
        for root in discovery_roots() {
            if !root.is_dir() {
                continue;
            }
            load_from_dir(&mut reg, &root)?;
        }
        // Fill gaps with official manifests embedded in the binary (pip installs).
        for manifest in crate::extensions::bundled::official_manifests() {
            if reg.by_name.contains_key(&manifest.name) {
                continue;
            }
            if manifest
                .trigger_types
                .iter()
                .any(|t| reg.trigger_index.contains_key(t))
            {
                continue;
            }
            let dir = extensions_dir().join(&manifest.name);
            reg.insert(InstalledExtension {
                name: manifest.name.clone(),
                dir,
                manifest,
            })?;
        }
        Ok(reg)
    }

    pub fn insert(&mut self, installed: InstalledExtension) -> Result<(), CurupiraError> {
        if self.by_name.contains_key(&installed.name) {
            return Err(CurupiraError::Plugin(format!(
                "duplicate extension name {:?}",
                installed.name
            )));
        }
        for trigger in &installed.manifest.trigger_types {
            if let Some(other) = self.trigger_index.get(trigger) {
                return Err(CurupiraError::Plugin(format!(
                    "trigger_type {trigger:?} claimed by both {other:?} and {:?}",
                    installed.name
                )));
            }
        }
        for trigger in &installed.manifest.trigger_types {
            self.trigger_index
                .insert(trigger.clone(), installed.name.clone());
        }
        self.by_name.insert(installed.name.clone(), installed);
        Ok(())
    }

    #[must_use]
    pub fn get(&self, name: &str) -> Option<&InstalledExtension> {
        self.by_name.get(name)
    }

    #[must_use]
    pub fn extension_for_trigger(&self, trigger_type: &str) -> Option<&str> {
        self.trigger_index.get(trigger_type).map(String::as_str)
    }

    pub fn iter(&self) -> impl Iterator<Item = &InstalledExtension> {
        self.by_name.values()
    }

    /// Persist a manifest into the registry directory.
    pub fn write_manifest(dir: &Path, manifest: &ExtensionManifest) -> Result<(), CurupiraError> {
        fs::create_dir_all(dir).map_err(|e| CurupiraError::Plugin(e.to_string()))?;
        let text = manifest
            .to_toml_string()
            .map_err(|e| CurupiraError::Plugin(e.to_string()))?;
        fs::write(dir.join(MANIFEST_FILE_NAME), text)
            .map_err(|e| CurupiraError::Plugin(e.to_string()))?;
        Ok(())
    }
}

fn discovery_roots() -> Vec<PathBuf> {
    let mut roots = vec![extensions_dir()];
    if let Ok(raw) = std::env::var("CURUPIRA_EXTENSIONS_PATH") {
        for part in raw.split([':', ';']) {
            if !part.is_empty() {
                roots.push(PathBuf::from(part));
            }
        }
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            roots.push(dir.join("plugins"));
            roots.push(dir.join("../share/curupira/plugins"));
        }
    }
    // Repository-relative default when developing from a checkout.
    let cwd_plugins = PathBuf::from("packages/plugins");
    if cwd_plugins.is_dir() {
        roots.push(cwd_plugins);
    }
    roots
}

fn load_from_dir(reg: &mut ExtensionRegistry, root: &Path) -> Result<(), CurupiraError> {
    let mut entries: Vec<_> = fs::read_dir(root)
        .map_err(|e| CurupiraError::Plugin(e.to_string()))?
        .filter_map(|e| e.ok())
        .collect();
    entries.sort_by_key(|e| e.file_name());
    for entry in entries {
        let path = entry.path();
        // Support both plugins/<name>/curupira-extension.toml and nested package dirs.
        let candidates = [
            path.join(MANIFEST_FILE_NAME),
            path.join("curupira-extension.toml"),
        ];
        let manifest_path = candidates.into_iter().find(|p| p.is_file());
        let Some(manifest_path) = manifest_path else {
            continue;
        };
        let text =
            fs::read_to_string(&manifest_path).map_err(|e| CurupiraError::Plugin(e.to_string()))?;
        let manifest = ExtensionManifest::from_toml_str(&text)
            .map_err(|e| CurupiraError::Plugin(format!("{}: {e}", manifest_path.display())))?;
        // Skip obsolete coding-agent manifests left on disk from older installs.
        if let Err(err) = manifest.validate() {
            if err.contains("coding-agent") {
                tracing::warn!(
                    "ignoring obsolete extension manifest {}: {err}",
                    manifest.name
                );
                continue;
            }
            return Err(CurupiraError::Plugin(format!("{}: {err}", manifest.name)));
        }
        if reg.by_name.contains_key(&manifest.name) {
            // Managed installs win over bundled copies with the same name.
            continue;
        }
        // Skip duplicate trigger claims from later roots.
        if manifest
            .trigger_types
            .iter()
            .any(|t| reg.trigger_index.contains_key(t))
        {
            continue;
        }
        reg.insert(InstalledExtension {
            name: manifest.name.clone(),
            dir: path,
            manifest,
        })?;
    }
    Ok(())
}

/// Human-readable lines for `plugins list` (manifest-only; no process spawn).
pub fn describe_installed(registry: &ExtensionRegistry) -> Result<Vec<String>, CurupiraError> {
    let mut lines = Vec::new();
    // Built-in cron
    lines.push(format!(
        "cron\tcurupira {VERSION} (built-in)\tprompt fields: -"
    ));
    for provider_name in known_providers() {
        let provider = AgentProvider::parse(provider_name).expect("known provider");
        lines.push(format!(
            "agent:{}\tcurupira {VERSION} (built-in)\texecutable: {}",
            provider.as_str(),
            provider.executable()
        ));
    }
    for ext in registry.iter() {
        let origin = format!("{} {}", ext.manifest.name, ext.manifest.version);
        for trigger in &ext.manifest.trigger_types {
            lines.push(format!(
                "{trigger}\t{origin}\tprompt fields: (see extension)"
            ));
        }
    }
    lines.sort();
    // Keep cron first for stability with historic tests that may look for it
    lines.sort_by(|a, b| {
        let a_cron = a.starts_with("cron\t");
        let b_cron = b.starts_with("cron\t");
        match (a_cron, b_cron) {
            (true, false) => std::cmp::Ordering::Less,
            (false, true) => std::cmp::Ordering::Greater,
            _ => a.cmp(b),
        }
    });
    Ok(lines)
}
