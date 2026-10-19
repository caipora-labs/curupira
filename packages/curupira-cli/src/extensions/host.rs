//! Spawn an extension process and speak JSON-RPC over stdin/stdout.

use std::collections::BTreeMap;
use std::io::{BufReader, Write};
use std::process::{Child, ChildStdin, ChildStdout, Stdio};

use crate::protocol::{
    negotiate, read_frame, write_frame, ClientInfo, DescribeResult, ErrorCode, InitializeParams,
    InitializeResult, KeyValue, Request, Response, TriggerLifecycleParams, TriggerPollParams,
    TriggerPollResult, TriggerSchemaParams, TriggerSchemaResult, TriggerValidateParams,
    TriggerValidateResult, CURRENT_PROTOCOL_VERSION, DEFAULT_MAX_FRAME_BYTES, METHOD_DESCRIBE,
    METHOD_INITIALIZE, METHOD_SHUTDOWN, METHOD_TRIGGER_ON_FINISHED, METHOD_TRIGGER_ON_STARTED,
    METHOD_TRIGGER_POLL, METHOD_TRIGGER_SCHEMA, METHOD_TRIGGER_VALIDATE,
};
use serde::de::DeserializeOwned;
use serde::Serialize;

use crate::error::CurupiraError;
use crate::extensions::registry::InstalledExtension;
use crate::process::apply_spawn_environment;
use crate::version::VERSION;

/// Live JSON-RPC extension session.
pub struct ExtensionHost {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
    next_id: u64,
    max_frame: u32,
}

impl ExtensionHost {
    /// Spawn from a registry entry and complete `initialize`.
    pub fn spawn(
        installed: &InstalledExtension,
        env_vars: &BTreeMap<String, String>,
    ) -> Result<Self, CurupiraError> {
        let (program, args) = resolve_launch(&installed.manifest.launch)?;
        Self::spawn_command(installed, &program, &args, env_vars)
    }

    /// Spawn using a `[plugins.<alias>]` launcher (`uvx` / `npx` + args).
    pub fn spawn_plugin(
        alias: &str,
        launch: &crate::config::PluginConfiguration,
        env_vars: &BTreeMap<String, String>,
    ) -> Result<Self, CurupiraError> {
        let (program, args) = launch.resolve_command()?;
        Self::spawn_argv(alias, &program, &args, None, env_vars)
    }

    /// Spawn using a registry manifest launch (managed installs / fixtures).
    fn spawn_command(
        installed: &InstalledExtension,
        program: &str,
        args: &[String],
        env_vars: &BTreeMap<String, String>,
    ) -> Result<Self, CurupiraError> {
        let cwd = installed.dir.is_dir().then_some(installed.dir.as_path());
        Self::spawn_argv(&installed.name, program, args, cwd, env_vars)
    }

    fn spawn_argv(
        name: &str,
        program: &str,
        args: &[String],
        cwd: Option<&std::path::Path>,
        env_vars: &BTreeMap<String, String>,
    ) -> Result<Self, CurupiraError> {
        let mut command = crate::process::std_command(program, args).map_err(|e| {
            CurupiraError::Plugin(format!(
                "failed to start extension {name}: {e} (program {program:?})"
            ))
        })?;
        command
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::inherit());
        // Ensure official in-tree modules resolve when developing from a checkout.
        // Paths must be absolute: children often run with cwd = the extension directory.
        // This pair is applied after `[environment.vars]`, so the checkout path wins.
        let mut extra = Vec::new();
        if let Some(pythonpath) = resolve_extension_pythonpath() {
            extra.push(("PYTHONPATH".into(), pythonpath));
        }
        apply_spawn_environment(&mut command, env_vars, &extra, cwd);
        let mut child = command.spawn().map_err(|e| {
            CurupiraError::Plugin(format!(
                "failed to start extension {name}: {e} (program {program:?})"
            ))
        })?;
        let stdin = child
            .stdin
            .take()
            .ok_or_else(|| CurupiraError::Plugin("extension stdin missing".into()))?;
        let stdout = child
            .stdout
            .take()
            .ok_or_else(|| CurupiraError::Plugin("extension stdout missing".into()))?;
        let mut host = Self {
            child,
            stdin,
            stdout: BufReader::new(stdout),
            next_id: 1,
            max_frame: DEFAULT_MAX_FRAME_BYTES,
        };
        let init: InitializeResult = host.call(
            METHOD_INITIALIZE,
            InitializeParams {
                protocol_version: CURRENT_PROTOCOL_VERSION,
                client_info: ClientInfo {
                    name: "curupira".into(),
                    version: VERSION.into(),
                },
            },
        )?;
        negotiate(init.protocol_version).map_err(CurupiraError::Plugin)?;
        Ok(host)
    }

    pub fn describe(&mut self) -> Result<DescribeResult, CurupiraError> {
        self.call(METHOD_DESCRIBE, ())
    }

    pub fn trigger_schema(
        &mut self,
        trigger_type: &str,
    ) -> Result<TriggerSchemaResult, CurupiraError> {
        self.call(
            METHOD_TRIGGER_SCHEMA,
            TriggerSchemaParams {
                trigger_type: trigger_type.into(),
            },
        )
    }

    pub fn validate_trigger(
        &mut self,
        trigger_type: &str,
        configuration: &serde_json::Value,
    ) -> Result<TriggerValidateResult, CurupiraError> {
        self.call(
            METHOD_TRIGGER_VALIDATE,
            TriggerValidateParams {
                trigger_type: trigger_type.into(),
                configuration: configuration.clone(),
            },
        )
    }

    pub fn poll_trigger(
        &mut self,
        trigger_type: &str,
        automation: &serde_json::Value,
        preview: bool,
        limit: u32,
    ) -> Result<TriggerPollResult, CurupiraError> {
        self.call(
            METHOD_TRIGGER_POLL,
            TriggerPollParams {
                trigger_type: trigger_type.into(),
                automation: automation.clone(),
                preview,
                limit,
            },
        )
    }

    pub fn on_started(
        &mut self,
        trigger_type: &str,
        values: &[KeyValue],
    ) -> Result<(), CurupiraError> {
        let _: serde_json::Value = self.call(
            METHOD_TRIGGER_ON_STARTED,
            TriggerLifecycleParams {
                trigger_type: trigger_type.into(),
                values: values.to_vec(),
            },
        )?;
        Ok(())
    }

    pub fn on_finished(
        &mut self,
        trigger_type: &str,
        values: &[KeyValue],
    ) -> Result<(), CurupiraError> {
        let _: serde_json::Value = self.call(
            METHOD_TRIGGER_ON_FINISHED,
            TriggerLifecycleParams {
                trigger_type: trigger_type.into(),
                values: values.to_vec(),
            },
        )?;
        Ok(())
    }

    pub fn shutdown(&mut self) -> Result<(), CurupiraError> {
        let _ = self.call::<_, serde_json::Value>(METHOD_SHUTDOWN, ());
        let _ = self.child.kill();
        let _ = self.child.wait();
        Ok(())
    }

    fn call<P: Serialize, R: DeserializeOwned>(
        &mut self,
        method: &str,
        params: P,
    ) -> Result<R, CurupiraError> {
        let id = self.next_id;
        self.next_id += 1;
        let params_value = serde_json::to_value(params)
            .map_err(|e| CurupiraError::Plugin(format!("encode params: {e}")))?;
        let request = Request::new(id, method, Some(params_value));
        let payload = serde_json::to_vec(&request)
            .map_err(|e| CurupiraError::Plugin(format!("encode request: {e}")))?;
        write_frame(&mut self.stdin, &payload)
            .map_err(|e| CurupiraError::Plugin(format!("transport write: {e}")))?;
        self.stdin
            .flush()
            .map_err(|e| CurupiraError::Plugin(format!("transport flush: {e}")))?;

        // Blocking read with a soft timeout via thread — keep simple for portability.
        let body = read_frame(&mut self.stdout, self.max_frame).map_err(|e| {
            CurupiraError::Plugin(format!(
                "transport read ({method}): {e} [{}]",
                ErrorCode::TRANSPORT.0
            ))
        })?;
        let response: Response = serde_json::from_slice(&body).map_err(|e| {
            CurupiraError::Plugin(format!(
                "invalid JSON-RPC response: {e} [{}]",
                ErrorCode::PROTOCOL.0
            ))
        })?;
        if let Some(err) = response.error {
            return Err(CurupiraError::Plugin(format!(
                "{} ({})",
                err.message, err.code.0
            )));
        }
        let result = response.result.ok_or_else(|| {
            CurupiraError::Plugin(format!("missing result [{}]", ErrorCode::PROTOCOL.0))
        })?;
        serde_json::from_value(result)
            .map_err(|e| CurupiraError::Plugin(format!("decode result for {method}: {e}")))
    }
}

impl Drop for ExtensionHost {
    fn drop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

/// Build an absolute `PYTHONPATH` for extension children.
fn resolve_extension_pythonpath() -> Option<String> {
    let mut entries: Vec<String> = Vec::new();
    if let Ok(extra) = std::env::var("CURUPIRA_PYTHONPATH") {
        for part in extra.split([':', ';']) {
            if part.is_empty() {
                continue;
            }
            entries.push(absolutize_path_entry(part));
        }
    }
    if let Ok(existing) = std::env::var("PYTHONPATH") {
        for part in existing.split([':', ';']) {
            if part.is_empty() {
                continue;
            }
            let abs = absolutize_path_entry(part);
            if !entries.iter().any(|e| e == &abs) {
                entries.push(abs);
            }
        }
    }
    if entries.is_empty() {
        None
    } else {
        Some(entries.join(":"))
    }
}

fn absolutize_path_entry(raw: &str) -> String {
    let path = std::path::PathBuf::from(raw);
    if path.is_absolute() {
        return path.display().to_string();
    }
    match std::env::current_dir() {
        Ok(cwd) => cwd.join(path).display().to_string(),
        Err(_) => raw.to_string(),
    }
}

fn resolve_launch(
    launch: &crate::protocol::LaunchSpec,
) -> Result<(String, Vec<String>), CurupiraError> {
    use crate::protocol::LaunchSpec;
    match launch {
        LaunchSpec::Executable { program, args } => Ok((program.clone(), args.clone())),
        LaunchSpec::Uvx {
            package,
            version,
            executable,
            args,
        } => {
            let uvx = which::which("uvx").map_err(|_| {
                CurupiraError::Plugin(
                    "uvx is required to run Python extensions but was not found on PATH".into(),
                )
            })?;
            let mut argv = vec!["--from".into()];
            if let Some(ver) = version {
                argv.push(format!("{package}=={ver}"));
            } else {
                argv.push(package.clone());
            }
            argv.push(executable.clone());
            argv.extend(args.clone());
            Ok((uvx.to_string_lossy().into_owned(), argv))
        }
        LaunchSpec::Npx {
            package,
            version,
            bin,
            args,
        } => {
            let npx = which::which("npx").map_err(|_| {
                CurupiraError::Plugin(
                    "npx is required to run Node extensions but was not found on PATH; \
                     install Node.js from https://nodejs.org/ so the npx command is available"
                        .into(),
                )
            })?;
            let mut argv = vec!["--yes".into()];
            if let Some(ver) = version {
                argv.push(format!("{package}@{ver}"));
            } else {
                argv.push(package.clone());
            }
            if let Some(bin) = bin {
                argv.push("--".into());
                argv.push(bin.clone());
            }
            argv.extend(args.clone());
            Ok((npx.to_string_lossy().into_owned(), argv))
        }
    }
}
