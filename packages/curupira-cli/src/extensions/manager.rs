//! Install / uninstall managed extensions (pip / npm / local path).

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use crate::process::apply_spawn_environment;

use crate::protocol::{
    ExtensionKind, ExtensionManifest, ExtensionRuntime, LaunchSpec, PackageRef, MANIFEST_FILE_NAME,
};

use crate::error::CurupiraError;
use crate::extensions::registry::ExtensionRegistry;
use crate::runtime::extensions_dir;

/// Parsed install source.
#[derive(Debug, Clone)]
pub enum ExtensionSource {
    Pip {
        package: String,
        version: Option<String>,
    },
    Npm {
        package: String,
        version: Option<String>,
    },
    Path {
        path: PathBuf,
    },
}

impl ExtensionSource {
    pub fn parse(raw: &str) -> Result<Self, CurupiraError> {
        if let Some(rest) = raw.strip_prefix("pip:") {
            let (package, version) = split_pip(rest)?;
            validate_package_name(&package)?;
            return Ok(Self::Pip { package, version });
        }
        if let Some(rest) = raw.strip_prefix("npm:") {
            let (package, version) = split_npm(rest)?;
            validate_package_name(&package)?;
            return Ok(Self::Npm { package, version });
        }
        if let Some(rest) = raw.strip_prefix("path:") {
            return Ok(Self::Path {
                path: PathBuf::from(rest),
            });
        }
        // bare path for local manifests
        let path = PathBuf::from(raw);
        if path.exists() {
            return Ok(Self::Path { path });
        }
        Err(CurupiraError::Plugin(format!(
            "unsupported extension source {raw:?}; use pip:<pkg>, npm:<pkg>, or path:<dir>"
        )))
    }
}

fn split_pip(spec: &str) -> Result<(String, Option<String>), CurupiraError> {
    if let Some((pkg, ver)) = spec.split_once("==") {
        Ok((pkg.to_string(), Some(ver.to_string())))
    } else {
        Ok((spec.to_string(), None))
    }
}

fn split_npm(spec: &str) -> Result<(String, Option<String>), CurupiraError> {
    // support @scope/name@version and name@version
    if spec.starts_with('@') {
        if let Some(idx) = spec.rfind('@') {
            if idx > 0 {
                return Ok((spec[..idx].to_string(), Some(spec[idx + 1..].to_string())));
            }
        }
        return Ok((spec.to_string(), None));
    }
    if let Some((pkg, ver)) = spec.split_once('@') {
        Ok((pkg.to_string(), Some(ver.to_string())))
    } else {
        Ok((spec.to_string(), None))
    }
}

fn validate_package_name(name: &str) -> Result<(), CurupiraError> {
    if name.is_empty()
        || name.contains("..")
        || name.contains('/') && !name.starts_with('@')
        || name.contains('\\')
        || name.contains(' ')
        || name.contains(';')
        || name.contains('|')
        || name.contains('&')
    {
        return Err(CurupiraError::Plugin(format!(
            "invalid package name {name:?}"
        )));
    }
    Ok(())
}

/// Install an extension and write its manifest into the registry.
///
/// `env_vars` are `[environment.vars]` overwrites for the `uvx` / `npx` probe. An empty
/// map still replicates the Curupira process environment.
pub fn install_extension(
    source: &ExtensionSource,
    env_vars: &BTreeMap<String, String>,
) -> Result<ExtensionManifest, CurupiraError> {
    match source {
        ExtensionSource::Path { path } => install_from_path(path),
        ExtensionSource::Pip { package, version } => {
            // Resolve manifest by running a one-shot metadata probe is disallowed during discovery.
            // Convention: package must ship a console script `<package-name.replace('_','-')>-ext`
            // and we write a provisional manifest; `plugins info` / first use validates via initialize.
            let executable = format!("{}-ext", package.replace('_', "-"));
            let name = package.replace('_', "-");
            let manifest = ExtensionManifest {
                manifest_version: 1,
                name: name.clone(),
                version: version.clone().unwrap_or_else(|| "*".into()),
                protocol_version: 2,
                runtime: ExtensionRuntime::Python,
                kind: ExtensionKind::Trigger,
                launch: LaunchSpec::Uvx {
                    package: package.clone(),
                    version: version.clone(),
                    executable,
                    args: vec![],
                },
                package: Some(PackageRef {
                    source: "pip".into(),
                    name: package.clone(),
                    version: version.clone(),
                }),
                capabilities: Default::default(),
                trigger_types: vec!["*".into()],
                agent_providers: vec![],
            };
            // Pre-fetch with uvx once so install fails closed without leaving a half registry entry.
            ensure_uvx()?;
            let dir = extensions_dir().join(&name);
            // Prefer vendor-provided manifest if the user pointed at a wheel later; for pip we
            // require the package to expose `curupira-extension.toml` via a known data file after
            // a controlled `uvx` print-manifest helper:
            let resolved = fetch_pip_manifest(package, version.as_deref(), env_vars)?;
            ExtensionRegistry::write_manifest(&dir, &resolved)?;
            let _ = manifest;
            Ok(resolved)
        }
        ExtensionSource::Npm { package, version } => {
            ensure_npx()?;
            let resolved = fetch_npm_manifest(package, version.as_deref(), env_vars)?;
            let dir = extensions_dir().join(&resolved.name);
            ExtensionRegistry::write_manifest(&dir, &resolved)?;
            Ok(resolved)
        }
    }
}

fn install_from_path(path: &Path) -> Result<ExtensionManifest, CurupiraError> {
    let manifest_path = if path.is_file() {
        path.to_path_buf()
    } else {
        path.join(MANIFEST_FILE_NAME)
    };
    let text = fs::read_to_string(&manifest_path).map_err(|e| {
        CurupiraError::Plugin(format!("cannot read {}: {e}", manifest_path.display()))
    })?;
    let manifest = ExtensionManifest::from_toml_str(&text)
        .map_err(|e| CurupiraError::Plugin(e.to_string()))?;
    manifest.validate().map_err(CurupiraError::Plugin)?;
    let dir = extensions_dir().join(&manifest.name);
    ExtensionRegistry::write_manifest(&dir, &manifest)?;
    // Copy sidecar launch scripts if present next to the manifest.
    if path.is_dir() {
        for entry in fs::read_dir(path).map_err(|e| CurupiraError::Plugin(e.to_string()))? {
            let entry = entry.map_err(|e| CurupiraError::Plugin(e.to_string()))?;
            let dest = dir.join(entry.file_name());
            if entry.path().is_file() {
                let _ = fs::copy(entry.path(), dest);
            }
        }
    }
    Ok(manifest)
}

/// Ask a pip package to print its manifest via `python -m <pkg> --print-manifest` through uvx.
fn fetch_pip_manifest(
    package: &str,
    version: Option<&str>,
    env_vars: &BTreeMap<String, String>,
) -> Result<ExtensionManifest, CurupiraError> {
    let uvx = ensure_uvx()?;
    let from = match version {
        Some(v) => format!("{package}=={v}"),
        None => package.to_string(),
    };
    // Convention: `python -m <module> --curupira-print-manifest`
    let module = package.replace('-', "_");
    let program = uvx.to_string_lossy();
    let args = vec![
        "--from".into(),
        from,
        "python".into(),
        "-m".into(),
        module,
        "--curupira-print-manifest".into(),
    ];
    let mut command = crate::process::std_command(&program, &args)
        .map_err(|e| CurupiraError::Plugin(format!("uvx failed: {e}")))?;
    apply_spawn_environment(&mut command, env_vars, &[], None);
    let output = command
        .output()
        .map_err(|e| CurupiraError::Plugin(format!("uvx failed: {e}")))?;
    if !output.status.success() {
        return Err(CurupiraError::Plugin(format!(
            "failed to fetch manifest from pip package {package}: {}",
            String::from_utf8_lossy(&output.stderr)
        )));
    }
    let text = String::from_utf8_lossy(&output.stdout);
    let manifest = ExtensionManifest::from_toml_str(text.trim())
        .map_err(|e| CurupiraError::Plugin(e.to_string()))?;
    manifest.validate().map_err(CurupiraError::Plugin)?;
    Ok(manifest)
}

fn fetch_npm_manifest(
    package: &str,
    version: Option<&str>,
    env_vars: &BTreeMap<String, String>,
) -> Result<ExtensionManifest, CurupiraError> {
    let npx = ensure_npx()?;
    let spec = match version {
        Some(v) => format!("{package}@{v}"),
        None => package.to_string(),
    };
    let program = npx.to_string_lossy();
    let args = vec!["--yes".into(), spec, "--curupira-print-manifest".into()];
    let mut command = crate::process::std_command(&program, &args)
        .map_err(|e| CurupiraError::Plugin(format!("npx failed: {e}")))?;
    apply_spawn_environment(&mut command, env_vars, &[], None);
    let output = command
        .output()
        .map_err(|e| CurupiraError::Plugin(format!("npx failed: {e}")))?;
    if !output.status.success() {
        return Err(CurupiraError::Plugin(format!(
            "failed to fetch manifest from npm package {package}: {}",
            String::from_utf8_lossy(&output.stderr)
        )));
    }
    let text = String::from_utf8_lossy(&output.stdout);
    let manifest = ExtensionManifest::from_toml_str(text.trim())
        .map_err(|e| CurupiraError::Plugin(e.to_string()))?;
    manifest.validate().map_err(CurupiraError::Plugin)?;
    Ok(manifest)
}

pub fn uninstall_extension(name: &str) -> Result<(), CurupiraError> {
    let dir = extensions_dir().join(name);
    if !dir.is_dir() {
        return Err(CurupiraError::Plugin(format!(
            "extension {name:?} is not installed"
        )));
    }
    fs::remove_dir_all(&dir).map_err(|e| CurupiraError::Plugin(e.to_string()))?;
    Ok(())
}

fn ensure_uvx() -> Result<PathBuf, CurupiraError> {
    which::which("uvx").map_err(|_| {
        CurupiraError::Plugin("uvx not found on PATH (install uv to use pip: extensions)".into())
    })
}

fn ensure_npx() -> Result<PathBuf, CurupiraError> {
    which::which("npx").map_err(|_| {
        CurupiraError::Plugin(
            "npx not found on PATH; install Node.js from https://nodejs.org/ \
             to use npm: extensions (the npx command must be available)"
                .into(),
        )
    })
}
