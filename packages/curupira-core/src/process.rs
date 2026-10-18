//! Headless subprocess runner (argv only; never a shell string).

use std::collections::BTreeMap;
use std::ffi::OsStr;
use std::path::Path;
use std::process::Stdio;
use std::time::Duration;

use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::process::Command;
use tokio::time::timeout;

/// Git variables that bind a process to one repository or index; cleared for task worktrees.
const REPOSITORY_BINDING_ENV: &[&str] = &[
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_NAMESPACE",
];

/// Bounded process result.
#[derive(Debug, Clone)]
pub struct ProcessResult {
    pub exit_code: i32,
    pub stdout: Vec<u8>,
    pub stderr: Vec<u8>,
}

/// Command builder surface shared by the std and tokio process APIs.
pub(crate) trait SpawnCommand {
    fn clear_env(&mut self);
    fn set_env(&mut self, key: &OsStr, val: &OsStr);
    fn remove_env(&mut self, key: &OsStr);
    fn set_current_dir(&mut self, dir: &Path);
}

impl SpawnCommand for std::process::Command {
    fn clear_env(&mut self) {
        self.env_clear();
    }

    fn set_env(&mut self, key: &OsStr, val: &OsStr) {
        self.env(key, val);
    }

    fn remove_env(&mut self, key: &OsStr) {
        self.env_remove(key);
    }

    fn set_current_dir(&mut self, dir: &Path) {
        self.current_dir(dir);
    }
}

impl SpawnCommand for Command {
    fn clear_env(&mut self) {
        self.env_clear();
    }

    fn set_env(&mut self, key: &OsStr, val: &OsStr) {
        self.env(key, val);
    }

    fn remove_env(&mut self, key: &OsStr) {
        self.env_remove(key);
    }

    fn set_current_dir(&mut self, dir: &Path) {
        self.current_dir(dir);
    }
}

/// Give a child a copy of Curupira's environment, then apply overwrites.
///
/// Order:
/// 1. Drop implicit inheritance (`env_clear`).
/// 2. Copy every variable the current process can see (`std::env::vars_os`).
/// 3. Replace keys from `[environment.vars]` (`overrides`).
/// 4. Apply call-site pairs (`extra`), such as an agent's database path.
/// 5. When `cwd` is set, point `PWD` at that directory and drop `OLDPWD` plus the
///    repository-binding `GIT_*` variables, even if an earlier step set them.
pub(crate) fn apply_spawn_environment(
    command: &mut impl SpawnCommand,
    overrides: &BTreeMap<String, String>,
    extra: &[(String, String)],
    cwd: Option<&Path>,
) {
    command.clear_env();
    for (key, value) in std::env::vars_os() {
        command.set_env(&key, &value);
    }
    for (key, value) in overrides {
        command.set_env(OsStr::new(key), OsStr::new(value));
    }
    for (key, value) in extra {
        command.set_env(OsStr::new(key), OsStr::new(value));
    }
    if let Some(dir) = cwd {
        command.set_current_dir(dir);
        // Tools read PWD (and Git reads GIT_*) instead of the kernel cwd. Without this, an
        // agent started in a task worktree inherits the caller's PWD and repository binding
        // and can act on the caller's checkout.
        command.set_env(OsStr::new("PWD"), dir.as_os_str());
        command.remove_env(OsStr::new("OLDPWD"));
        for var in REPOSITORY_BINDING_ENV {
            command.remove_env(OsStr::new(var));
        }
    }
}

/// Run an executable with an argument vector, timeout, and retained output tails.
///
/// `env_overrides` are `[environment.vars]` replacements applied on top of a full copy of
/// this process's environment. `env` is applied after those replacements.
pub async fn run_process(
    program: &str,
    args: &[String],
    cwd: Option<&std::path::Path>,
    env: &[(String, String)],
    env_overrides: &BTreeMap<String, String>,
    timeout_duration: Duration,
    max_output_bytes: usize,
) -> Result<ProcessResult, String> {
    let mut cmd = Command::new(program);
    cmd.args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true);
    apply_spawn_environment(&mut cmd, env_overrides, env, cwd);
    // Platform process-group isolation is applied by the OS defaults; kill_on_drop
    // covers timeout cancellation for the direct child.

    let mut child = cmd.spawn().map_err(|e| format!("spawn {program}: {e}"))?;
    let mut stdout = child
        .stdout
        .take()
        .ok_or_else(|| "missing stdout".to_string())?;
    let mut stderr = child
        .stderr
        .take()
        .ok_or_else(|| "missing stderr".to_string())?;

    let stdout_task = tokio::spawn(async move {
        let mut buf = Vec::new();
        let mut chunk = [0_u8; 8192];
        loop {
            match stdout.read(&mut chunk).await {
                Ok(0) => break,
                Ok(n) => {
                    buf.extend_from_slice(&chunk[..n]);
                    if buf.len() > max_output_bytes {
                        let keep = max_output_bytes;
                        buf = buf[buf.len() - keep..].to_vec();
                    }
                }
                Err(_) => break,
            }
        }
        buf
    });
    let stderr_task = tokio::spawn(async move {
        let mut buf = Vec::new();
        let mut chunk = [0_u8; 8192];
        loop {
            match stderr.read(&mut chunk).await {
                Ok(0) => break,
                Ok(n) => {
                    buf.extend_from_slice(&chunk[..n]);
                    if buf.len() > max_output_bytes {
                        let keep = max_output_bytes;
                        buf = buf[buf.len() - keep..].to_vec();
                    }
                }
                Err(_) => break,
            }
        }
        buf
    });

    let wait = timeout(timeout_duration, child.wait());
    let status = match wait.await {
        Ok(Ok(status)) => status,
        Ok(Err(e)) => return Err(format!("wait: {e}")),
        Err(_) => {
            let _ = child.start_kill();
            let _ = child.wait().await;
            return Err(format!(
                "process timed out after {}s",
                timeout_duration.as_secs()
            ));
        }
    };

    let stdout = stdout_task.await.unwrap_or_default();
    let stderr = stderr_task.await.unwrap_or_default();
    Ok(ProcessResult {
        exit_code: status.code().unwrap_or(1),
        stdout,
        stderr,
    })
}

/// Write bytes to a child's stdin then close (unused helper for future setup scripts).
pub async fn write_all_close<W: AsyncWriteExt + Unpin>(
    writer: &mut W,
    data: &[u8],
) -> Result<(), String> {
    writer.write_all(data).await.map_err(|e| e.to_string())?;
    writer.shutdown().await.map_err(|e| e.to_string())?;
    Ok(())
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;

    #[tokio::test]
    async fn child_pwd_follows_its_working_directory() {
        let dir = tempfile::tempdir().unwrap();
        let expected = dir.path().canonicalize().unwrap();

        let result = run_process(
            "sh",
            &["-c".into(), "printf %s \"$PWD\"".into()],
            Some(dir.path()),
            &[],
            &BTreeMap::new(),
            Duration::from_secs(10),
            1024,
        )
        .await
        .unwrap();

        assert_eq!(result.exit_code, 0);
        let pwd = String::from_utf8(result.stdout).unwrap();
        assert_eq!(std::path::Path::new(&pwd).canonicalize().unwrap(), expected);
    }

    #[tokio::test]
    async fn child_copies_parent_env_and_applies_overrides() {
        let inherited = "CURUPIRA_SPAWN_INHERITED";
        let replaced = "CURUPIRA_SPAWN_OVERRIDE";
        let only_config = "CURUPIRA_SPAWN_ONLY_CONFIG";
        std::env::set_var(inherited, "from-parent");
        std::env::set_var(replaced, "parent-value");
        std::env::remove_var(only_config);

        let mut overrides = BTreeMap::new();
        overrides.insert(replaced.into(), "from-config".into());
        overrides.insert(only_config.into(), "config-only".into());

        let script = format!(
            "printf '%s\\n%s\\n%s' \"${{{inherited}}}\" \"${{{replaced}}}\" \"${{{only_config}}}\""
        );
        let result = run_process(
            "sh",
            &["-c".into(), script],
            None,
            &[],
            &overrides,
            Duration::from_secs(10),
            1024,
        )
        .await
        .unwrap();

        std::env::remove_var(inherited);
        std::env::remove_var(replaced);

        assert_eq!(
            result.exit_code,
            0,
            "{:?}",
            String::from_utf8_lossy(&result.stderr)
        );
        let stdout = String::from_utf8(result.stdout).unwrap();
        assert_eq!(stdout, "from-parent\nfrom-config\nconfig-only");
    }

    #[tokio::test]
    async fn call_site_env_and_workdir_win_over_overrides() {
        let dir = tempfile::tempdir().unwrap();
        let mut overrides = BTreeMap::new();
        overrides.insert("GIT_DIR".into(), "/should-not-leak".into());
        overrides.insert("CURUPIRA_SPAWN_EXTRA".into(), "from-config".into());
        overrides.insert("PWD".into(), "/not-the-workdir".into());

        let result = run_process(
            "sh",
            &[
                "-c".into(),
                "printf '%s\\n%s\\n%s' \"${GIT_DIR-unset}\" \"$CURUPIRA_SPAWN_EXTRA\" \"$PWD\""
                    .into(),
            ],
            Some(dir.path()),
            &[("CURUPIRA_SPAWN_EXTRA".into(), "from-extra".into())],
            &overrides,
            Duration::from_secs(10),
            1024,
        )
        .await
        .unwrap();

        assert_eq!(
            result.exit_code,
            0,
            "{:?}",
            String::from_utf8_lossy(&result.stderr)
        );
        let stdout = String::from_utf8(result.stdout).unwrap();
        let mut lines = stdout.lines();
        assert_eq!(lines.next(), Some("unset"));
        assert_eq!(lines.next(), Some("from-extra"));
        let pwd = std::path::Path::new(lines.next().unwrap())
            .canonicalize()
            .unwrap();
        assert_eq!(pwd, dir.path().canonicalize().unwrap());
    }
}
