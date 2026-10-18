//! TOML configuration loading and validation.

use std::collections::BTreeMap;
use std::fs;
use std::path::{Path, PathBuf};

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

use crate::agents::AgentProvider;
use crate::error::CurupiraError;
use crate::extensions::host::ExtensionHost;
use crate::protocol::KeyValue;

/// Process log level.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum LogLevel {
    Debug,
    Info,
    Warning,
    Error,
    Critical,
}

impl LogLevel {
    pub fn parse(raw: &str) -> Result<Self, String> {
        match raw.to_ascii_uppercase().as_str() {
            "DEBUG" => Ok(Self::Debug),
            "INFO" => Ok(Self::Info),
            "WARNING" => Ok(Self::Warning),
            "ERROR" => Ok(Self::Error),
            "CRITICAL" => Ok(Self::Critical),
            _ => Err(format!(
                "invalid log level {raw:?}; expected DEBUG, INFO, WARNING, ERROR, or CRITICAL"
            )),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApplicationSettings {
    #[serde(default)]
    pub settings: ExecutionSettings,
    pub repositories: BTreeMap<String, RepositoryConfiguration>,
    pub agents: AgentsSettings,
    /// Register installed trigger packages under a TOML alias.
    ///
    /// Automations address triggers as `<alias>/<local-trigger>`
    /// (for example `plugins-py/github-issues`).
    #[serde(default)]
    pub plugins: BTreeMap<String, PluginConfiguration>,
    pub automations: BTreeMap<String, AutomationTable>,
    #[serde(default)]
    pub assistant: AssistantSettings,
}

/// One `[plugins.<alias>]` entry: launcher (`uvx` / `npx`) plus argv after it.
///
/// Trigger types are discovered by spawning the process and calling `describe`,
/// then filtered by optional [`Self::tools`] globs.
///
/// ```toml
/// [plugins.plugins-py]
/// type = "uvx"
/// args = ["--from", "curupira-plugins", "curupira-plugins"]
/// tools = ["github-*"]
///
/// [plugins.acme-node]
/// type = "npx"
/// args = ["--yes", "@acme/curupira-ext@1.2.3"]
/// tools = ["*", "!internal-*"]
/// ```
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PluginConfiguration {
    /// How to start the extension process.
    #[serde(flatten)]
    pub launcher: PluginLauncher,
    /// Glob patterns selecting which local trigger names to expose.
    ///
    /// Empty (default) keeps every trigger from `describe`. Positive patterns
    /// (`github-*`, `*`) are includes; patterns starting with `!` (`!monday-*`)
    /// are excludes.
    #[serde(default)]
    pub tools: Vec<String>,
}

/// Launcher binary and argv for a `[plugins.<alias>]` entry.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum PluginLauncher {
    /// Run `uvx` with the given args (never a shell string).
    Uvx {
        /// Arguments passed to `uvx`.
        args: Vec<String>,
    },
    /// Run `npx` with the given args (never a shell string).
    Npx {
        /// Arguments passed to `npx`.
        args: Vec<String>,
    },
}

impl PluginConfiguration {
    /// Resolve `uvx`/`npx` on PATH and return `(program, args)` for the child process.
    pub fn resolve_command(&self) -> Result<(String, Vec<String>), CurupiraError> {
        match &self.launcher {
            PluginLauncher::Uvx { args } => {
                if args.is_empty() {
                    return Err(CurupiraError::Config(
                        "plugins entry type = \"uvx\" requires a non-empty args array".into(),
                    ));
                }
                let uvx = which::which("uvx").map_err(|_| {
                    CurupiraError::Config(
                        "uvx is required for plugins with type = \"uvx\" but was not found on PATH"
                            .into(),
                    )
                })?;
                Ok((uvx.to_string_lossy().into_owned(), args.clone()))
            }
            PluginLauncher::Npx { args } => {
                if args.is_empty() {
                    return Err(CurupiraError::Config(
                        "plugins entry type = \"npx\" requires a non-empty args array".into(),
                    ));
                }
                let npx = which::which("npx").map_err(|_| {
                    CurupiraError::Config(
                        "npx is required for plugins with type = \"npx\" but was not found on PATH; \
                         install Node.js from https://nodejs.org/ so the npx command is available"
                            .into(),
                    )
                })?;
                Ok((npx.to_string_lossy().into_owned(), args.clone()))
            }
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExecutionSettings {
    #[serde(default = "default_max_active")]
    pub max_active_tasks: u32,
    #[serde(default = "default_max_pending")]
    pub max_pending_tasks: u32,
    #[serde(default = "default_workspace")]
    pub workspace_dir: String,
    #[serde(default = "default_state_db")]
    pub state_db_path: String,
    #[serde(default)]
    pub otlp_endpoint: Option<String>,
    #[serde(default = "default_log_level")]
    pub log_level: LogLevel,
    #[serde(default = "default_timeout")]
    pub task_timeout_minutes: u32,
    #[serde(default = "default_max_output")]
    pub max_output_bytes: u64,
    #[serde(default)]
    pub polling: PollingSettings,
}

impl Default for ExecutionSettings {
    fn default() -> Self {
        Self {
            max_active_tasks: default_max_active(),
            max_pending_tasks: default_max_pending(),
            workspace_dir: default_workspace(),
            state_db_path: default_state_db(),
            otlp_endpoint: None,
            log_level: default_log_level(),
            task_timeout_minutes: default_timeout(),
            max_output_bytes: default_max_output(),
            polling: PollingSettings::default(),
        }
    }
}

fn default_max_active() -> u32 {
    1
}
fn default_max_pending() -> u32 {
    100
}
fn default_workspace() -> String {
    "~/.curupira/workspaces".into()
}
fn default_state_db() -> String {
    "~/.curupira/state.sqlite3".into()
}
fn default_log_level() -> LogLevel {
    LogLevel::Info
}
fn default_timeout() -> u32 {
    20
}
fn default_max_output() -> u64 {
    1_000_000
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PollingSettings {
    #[serde(default = "default_poll_interval")]
    pub poll_interval_seconds: u64,
    #[serde(default = "default_batch")]
    pub batch_size: u32,
    #[serde(default = "default_cron_poll")]
    pub cron_poll_interval_seconds: u64,
}

impl Default for PollingSettings {
    fn default() -> Self {
        Self {
            poll_interval_seconds: default_poll_interval(),
            batch_size: default_batch(),
            cron_poll_interval_seconds: default_cron_poll(),
        }
    }
}

fn default_poll_interval() -> u64 {
    30
}
fn default_batch() -> u32 {
    100
}
fn default_cron_poll() -> u64 {
    1
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RepositoryConfiguration {
    pub remote: String,
    #[serde(default)]
    pub path: Option<String>,
    #[serde(default)]
    pub setup_script: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentsSettings {
    pub defaults: AgentDefaults,
    pub profiles: BTreeMap<String, AgentProfile>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentDefaults {
    pub profile: String,
    #[serde(default = "default_tz")]
    pub timezone: String,
}

fn default_tz() -> String {
    "UTC".into()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentProfile {
    pub provider: String,
    #[serde(flatten)]
    pub extra: serde_json::Map<String, serde_json::Value>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct AssistantSettings {
    #[serde(default)]
    pub agent: Option<String>,
    #[serde(default)]
    pub model: Option<String>,
}

/// Raw automation table before trigger-specific validation.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AutomationTable {
    #[serde(default)]
    pub trigger_type: Option<String>,
    pub repository: String,
    pub prompt: String,
    #[serde(default)]
    pub profile: Option<String>,
    #[serde(default)]
    pub checkout: Option<String>,
    #[serde(flatten)]
    pub extra: serde_json::Map<String, serde_json::Value>,
}

impl AutomationTable {
    pub fn effective_trigger_type(&self) -> &str {
        if let Some(t) = &self.trigger_type {
            return t.as_str();
        }
        if self.extra.contains_key("schedule") {
            "cron"
        } else {
            // Legacy default: official plugins registered as `plugins-py`.
            "plugins-py/github-issues"
        }
    }
}

#[derive(Debug, Clone)]
pub struct ResolvedAutomation {
    pub automation_id: String,
    pub identity_repo: String,
    pub repository_alias: String,
    pub configuration: serde_json::Value,
    pub trigger_type: String,
    pub repository: RepositoryConfiguration,
    pub profile: AgentProfile,
    pub profile_name: String,
    pub prompt: String,
    pub checkout: String,
}

/// Load and validate settings from TOML.
pub fn load_settings(
    path: &Path,
    log_level_override: Option<LogLevel>,
) -> Result<ApplicationSettings, CurupiraError> {
    let text = fs::read_to_string(path)
        .map_err(|e| CurupiraError::Config(format!("cannot read {}: {e}", path.display())))?;
    let mut settings: ApplicationSettings = toml::from_str(&text)
        .map_err(|e| CurupiraError::Config(format!("invalid TOML in {}: {e}", path.display())))?;

    if settings.repositories.is_empty() {
        return Err(CurupiraError::Config(
            "repositories must contain at least one entry".into(),
        ));
    }
    if settings.automations.is_empty() {
        return Err(CurupiraError::Config(
            "automations must contain at least one entry".into(),
        ));
    }
    if settings.agents.profiles.is_empty() {
        return Err(CurupiraError::Config(
            "agents.profiles must contain at least one profile".into(),
        ));
    }
    if !settings
        .agents
        .profiles
        .contains_key(&settings.agents.defaults.profile)
    {
        return Err(CurupiraError::Config(format!(
            "agents.defaults.profile {:?} is not defined in agents.profiles",
            settings.agents.defaults.profile
        )));
    }

    validate_identifier_keys(&settings)?;
    validate_setup_scripts(&settings)?;
    validate_cross_references(&settings)?;
    validate_agent_providers(&settings)?;

    // Trigger-specific validation: cron in-process; others via extension RPC schema.
    validate_automations(&settings)?;

    if let Some(level) = log_level_override {
        settings.settings.log_level = level;
    }

    // Resolve relative paths against the config file directory.
    let base = path
        .parent()
        .map(Path::to_path_buf)
        .unwrap_or_else(|| PathBuf::from("."));
    settings.settings.workspace_dir = resolve_path_setting(&settings.settings.workspace_dir, &base);
    settings.settings.state_db_path = resolve_path_setting(&settings.settings.state_db_path, &base);

    Ok(settings)
}

fn validate_identifier_keys(settings: &ApplicationSettings) -> Result<(), CurupiraError> {
    let re_ok = |s: &str| {
        !s.is_empty()
            && s.chars()
                .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-')
    };
    for key in settings.repositories.keys() {
        if !re_ok(key) {
            return Err(CurupiraError::Config(format!(
                "invalid repository alias {key:?}"
            )));
        }
    }
    for key in settings.plugins.keys() {
        if !re_ok(key) {
            return Err(CurupiraError::Config(format!(
                "invalid plugins alias {key:?}"
            )));
        }
    }
    for (alias, plugin) in &settings.plugins {
        // Fail closed early if the launcher is missing or args are empty.
        plugin.resolve_command().map_err(|err| match err {
            CurupiraError::Config(msg) => CurupiraError::Config(format!("plugins.{alias}: {msg}")),
            other => other,
        })?;
    }
    for key in settings.automations.keys() {
        if !re_ok(key) {
            return Err(CurupiraError::Config(format!(
                "invalid automation name {key:?}"
            )));
        }
    }
    Ok(())
}

fn validate_setup_scripts(settings: &ApplicationSettings) -> Result<(), CurupiraError> {
    for (alias, repo) in &settings.repositories {
        if let Some(script) = &repo.setup_script {
            let path = Path::new(script);
            if path.is_absolute()
                || script.split(['/', '\\']).any(|p| p == "..")
                || script.contains("..")
            {
                return Err(CurupiraError::Config(format!(
                    "repository {alias:?} setup_script must be a relative path without '..'"
                )));
            }
        }
    }
    Ok(())
}

fn validate_cross_references(settings: &ApplicationSettings) -> Result<(), CurupiraError> {
    for (name, auto) in &settings.automations {
        if !settings.repositories.contains_key(&auto.repository) {
            return Err(CurupiraError::Config(format!(
                "automation {name:?} references unknown repository {:?}",
                auto.repository
            )));
        }
        let profile = auto
            .profile
            .as_deref()
            .unwrap_or(settings.agents.defaults.profile.as_str());
        if !settings.agents.profiles.contains_key(profile) {
            return Err(CurupiraError::Config(format!(
                "automation {name:?} references unknown profile {profile:?}"
            )));
        }
    }
    Ok(())
}

fn validate_agent_providers(settings: &ApplicationSettings) -> Result<(), CurupiraError> {
    for (name, profile) in &settings.agents.profiles {
        AgentProvider::parse(&profile.provider)
            .map_err(|err| CurupiraError::Config(format!("agents.profiles.{name}: {err}")))?;
    }
    if let Some(agent) = &settings.assistant.agent {
        AgentProvider::parse(agent)
            .map_err(|err| CurupiraError::Config(format!("assistant.agent: {err}")))?;
    }
    Ok(())
}

fn validate_automations(settings: &ApplicationSettings) -> Result<(), CurupiraError> {
    let namespace = crate::extensions::namespace::PluginNamespaceIndex::build(&settings.plugins)?;
    let mut host_cache: BTreeMap<String, ExtensionHost> = BTreeMap::new();

    for (name, auto) in &settings.automations {
        let trigger = auto.effective_trigger_type().to_string();
        if trigger == "cron" {
            crate::cron::validate_automation_table(auto)?;
            crate::prompt::check(name, &auto.prompt, Some(&[]))?;
            continue;
        }
        let binding = namespace.resolve(&trigger).ok_or_else(|| {
            CurupiraError::Config(format!(
                "automation {name:?}: no [plugins.<alias>] registration provides \
                 trigger_type {trigger:?} (register under [plugins.<alias>] with type/args \
                 and use <alias>/<trigger>)"
            ))
        })?;
        let cache_key = binding.alias.clone();
        let local_trigger = binding.local_trigger.clone();
        let host = if let Some(h) = host_cache.get_mut(&cache_key) {
            h
        } else {
            let host = ExtensionHost::spawn_plugin(&binding.alias, &binding.launch)?;
            host_cache.insert(cache_key.clone(), host);
            host_cache.get_mut(&cache_key).unwrap()
        };
        let fields = host.trigger_schema(&local_trigger)?.prompt_fields;
        // A trigger that declares no fields only gets its prompt syntax checked.
        crate::prompt::check(
            name,
            &auto.prompt,
            (!fields.is_empty()).then_some(&fields[..]),
        )?;
        let config_value = automation_to_json(auto);
        let result = host.validate_trigger(&local_trigger, &config_value)?;
        if !result.ok {
            return Err(CurupiraError::Config(format!(
                "automation {name:?}: {}",
                result
                    .error
                    .unwrap_or_else(|| "invalid configuration".into())
            )));
        }
    }

    for host in host_cache.values_mut() {
        let _ = host.shutdown();
    }
    Ok(())
}

pub fn automation_to_json(auto: &AutomationTable) -> serde_json::Value {
    let mut map = serde_json::Map::new();
    map.insert(
        "trigger_type".into(),
        serde_json::Value::String(auto.effective_trigger_type().into()),
    );
    map.insert(
        "repository".into(),
        serde_json::Value::String(auto.repository.clone()),
    );
    map.insert(
        "prompt".into(),
        serde_json::Value::String(auto.prompt.clone()),
    );
    if let Some(p) = &auto.profile {
        map.insert("profile".into(), serde_json::Value::String(p.clone()));
    }
    if let Some(c) = &auto.checkout {
        map.insert("checkout".into(), serde_json::Value::String(c.clone()));
    }
    for (k, v) in &auto.extra {
        map.insert(k.clone(), v.clone());
    }
    serde_json::Value::Object(map)
}

fn resolve_path_setting(value: &str, base: &Path) -> String {
    let expanded = if let Some(rest) = value.strip_prefix("~/") {
        dirs::home_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join(rest)
    } else if value == "~" {
        dirs::home_dir().unwrap_or_else(|| PathBuf::from("."))
    } else {
        let p = PathBuf::from(value);
        if p.is_absolute() {
            p
        } else {
            base.join(p)
        }
    };
    expanded.to_string_lossy().into_owned()
}

/// Expand `~` in a path string.
pub fn expand_user(path: &str) -> PathBuf {
    if let Some(rest) = path.strip_prefix("~/") {
        dirs::home_dir()
            .unwrap_or_else(|| PathBuf::from("."))
            .join(rest)
    } else if path == "~" {
        dirs::home_dir().unwrap_or_else(|| PathBuf::from("."))
    } else {
        PathBuf::from(path)
    }
}

/// Resolve automations for dispatch.
pub fn resolve_automations(
    settings: &ApplicationSettings,
) -> Result<Vec<ResolvedAutomation>, CurupiraError> {
    let namespace = crate::extensions::namespace::PluginNamespaceIndex::build(&settings.plugins)?;
    let mut host_cache: BTreeMap<String, ExtensionHost> = BTreeMap::new();
    let mut out = Vec::new();
    for (name, auto) in &settings.automations {
        let repo = settings
            .repositories
            .get(&auto.repository)
            .ok_or_else(|| {
                CurupiraError::Config(format!("missing repository {}", auto.repository))
            })?
            .clone();
        let profile_name = auto
            .profile
            .clone()
            .unwrap_or_else(|| settings.agents.defaults.profile.clone());
        let profile = settings
            .agents
            .profiles
            .get(&profile_name)
            .ok_or_else(|| CurupiraError::Config(format!("missing profile {profile_name}")))?
            .clone();
        let trigger_type = auto.effective_trigger_type().to_string();
        let mut configuration = automation_to_json(auto);
        if trigger_type == "cron" {
            if let Some(obj) = configuration.as_object_mut() {
                if !obj.contains_key("timezone") || obj["timezone"].is_null() {
                    obj.insert(
                        "timezone".into(),
                        serde_json::Value::String(settings.agents.defaults.timezone.clone()),
                    );
                }
            }
        } else if let Some(binding) = namespace.resolve(&trigger_type) {
            let cache_key = binding.alias.clone();
            let local_trigger = binding.local_trigger.clone();
            let host = if let Some(h) = host_cache.get_mut(&cache_key) {
                h
            } else {
                let host = ExtensionHost::spawn_plugin(&binding.alias, &binding.launch)?;
                host_cache.insert(cache_key.clone(), host);
                host_cache.get_mut(&cache_key).unwrap()
            };
            let result = host.validate_trigger(&local_trigger, &configuration)?;
            if !result.ok {
                return Err(CurupiraError::Config(format!(
                    "automation {name:?}: {}",
                    result
                        .error
                        .unwrap_or_else(|| "invalid configuration".into())
                )));
            }
            if let Some(normalized) = result.configuration {
                configuration = normalized;
            }
        }
        let forge = forge_identity(&repo.remote);
        out.push(ResolvedAutomation {
            automation_id: name.clone(),
            identity_repo: forge,
            repository_alias: auto.repository.clone(),
            configuration,
            trigger_type,
            repository: repo,
            profile,
            profile_name,
            prompt: auto.prompt.clone(),
            checkout: auto.checkout.clone().unwrap_or_else(|| "worktree".into()),
        });
    }
    for host in host_cache.values_mut() {
        let _ = host.shutdown();
    }
    Ok(out)
}

fn forge_identity(remote: &str) -> String {
    // owner/repo style when possible
    let trimmed = remote.trim_end_matches(".git");
    if let Some(idx) = trimmed.rfind('/') {
        let rest = &trimmed[idx + 1..];
        let parent = &trimmed[..idx];
        if let Some(idx2) = parent.rfind('/') {
            return format!("{}/{}", &parent[idx2 + 1..], rest);
        }
        return rest.to_string();
    }
    trimmed.to_string()
}

/// Shared task snapshot used across dispatch.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Task {
    pub identity: TaskIdentity,
    pub automation_id: String,
    /// Trigger result. Empty for cron and for an extension item that returned no pairs.
    pub values: Vec<KeyValue>,
    #[serde(default)]
    pub scheduled_for: Option<DateTime<Utc>>,
    pub prompt: String,
    pub trigger_type: String,
    pub profile_name: String,
    pub provider: String,
    pub repository_remote: String,
    pub repository_alias: String,
    #[serde(default)]
    pub repository_path: Option<String>,
    #[serde(default)]
    pub setup_script: Option<String>,
    pub checkout: String,
    pub workspace_dir: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TaskIdentity {
    pub automation_id: String,
    pub repo: String,
    pub task_type: String,
    pub id: String,
}

impl TaskIdentity {
    pub fn key(&self) -> String {
        format!(
            "{}:{}:{}:{}",
            self.automation_id, self.repo, self.task_type, self.id
        )
    }
}
