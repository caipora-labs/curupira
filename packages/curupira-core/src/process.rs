//! Headless subprocess runner (argv only; never a shell string).

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

/// Run an executable with an argument vector, timeout, and retained output tails.
pub async fn run_process(
    program: &str,
    args: &[String],
    cwd: Option<&std::path::Path>,
    env: &[(String, String)],
    timeout_duration: Duration,
    max_output_bytes: usize,
) -> Result<ProcessResult, String> {
    let mut cmd = Command::new(program);
    cmd.args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true);
    if let Some(dir) = cwd {
        cmd.current_dir(dir);
        // Tools read PWD (and Git reads GIT_*) instead of the kernel cwd. Without this, an
        // agent started in a task worktree inherits the caller's PWD and repository binding
        // and can act on the caller's checkout.
        cmd.env("PWD", dir).env_remove("OLDPWD");
        for var in REPOSITORY_BINDING_ENV {
            cmd.env_remove(var);
        }
    }
    for (k, v) in env {
        cmd.env(k, v);
    }
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
            Duration::from_secs(10),
            1024,
        )
        .await
        .unwrap();

        assert_eq!(result.exit_code, 0);
        let pwd = String::from_utf8(result.stdout).unwrap();
        assert_eq!(std::path::Path::new(&pwd).canonicalize().unwrap(), expected);
    }
}
