//! Git checkout, worktree, and setup-script management owned by the Rust core.

use std::collections::{BTreeMap, HashMap};
use std::path::{Path, PathBuf};
use std::sync::Arc;
use std::time::Duration;

use hex::encode as hex_encode;
use sha2::{Digest, Sha256};
use tokio::sync::Mutex;

use crate::config::{expand_user, ApplicationSettings, Task};
use crate::error::CurupiraError;
use crate::process::run_process;

/// Prepared workspace for one task execution.
#[derive(Debug, Clone)]
pub struct PreparedWorkspace {
    pub cwd: PathBuf,
    pub base_checkout: PathBuf,
    pub worktree: Option<WorktreeHandle>,
}

/// Worktree created for an isolated task run.
#[derive(Debug, Clone)]
pub struct WorktreeHandle {
    pub path: PathBuf,
    pub branch: String,
    pub base: PathBuf,
}

/// Serializes clone/worktree operations that share a base checkout path.
#[derive(Default)]
pub struct VersionControl {
    checkout_locks: Mutex<HashMap<PathBuf, Arc<Mutex<()>>>>,
}

impl VersionControl {
    #[must_use]
    pub fn new() -> Self {
        Self::default()
    }

    async fn lock_for(&self, path: &Path) -> Arc<Mutex<()>> {
        let mut map = self.checkout_locks.lock().await;
        map.entry(path.to_path_buf())
            .or_insert_with(|| Arc::new(Mutex::new(())))
            .clone()
    }

    /// Ensure the base checkout exists, optionally create a worktree, run setup.
    pub async fn prepare(
        &self,
        settings: &ApplicationSettings,
        task: &Task,
    ) -> Result<PreparedWorkspace, CurupiraError> {
        let base = base_checkout_path(settings, task);
        let lock = self.lock_for(&base).await;
        let _guard = lock.lock().await;

        let env_vars = &settings.environment.vars;
        let checkout = ensure_checkout(&task.repository_remote, &base, env_vars).await?;
        if checkout.cloned {
            if let Some(script) = &task.setup_script {
                run_setup_script(&checkout.path, script, settings).await?;
            }
        }

        if task.checkout == "main" {
            return Ok(PreparedWorkspace {
                cwd: checkout.path.clone(),
                base_checkout: checkout.path,
                worktree: None,
            });
        }

        let worktree = ensure_worktree(
            &checkout.path,
            &task.automation_id,
            &task.identity.task_type,
            &task.identity.id,
            env_vars,
        )
        .await?;
        Ok(PreparedWorkspace {
            cwd: worktree.path.clone(),
            base_checkout: checkout.path,
            worktree: Some(worktree),
        })
    }

    /// Remove a task worktree and its local branch (best-effort errors surface).
    ///
    /// `env_vars` are the `[environment.vars]` overwrites used for the git processes.
    pub async fn cleanup(
        &self,
        env_vars: &BTreeMap<String, String>,
        prepared: &PreparedWorkspace,
    ) -> Result<(), CurupiraError> {
        let Some(worktree) = &prepared.worktree else {
            return Ok(());
        };
        let lock = self.lock_for(&prepared.base_checkout).await;
        let _guard = lock.lock().await;
        remove_worktree(&prepared.base_checkout, worktree, env_vars).await
    }
}

#[derive(Debug, Clone)]
struct Checkout {
    path: PathBuf,
    cloned: bool,
}

fn base_checkout_path(settings: &ApplicationSettings, task: &Task) -> PathBuf {
    if let Some(path) = &task.repository_path {
        return expand_user(path);
    }
    let root = expand_user(&settings.settings.workspace_dir);
    root.join(&task.repository_alias)
}

async fn ensure_checkout(
    remote: &str,
    destination: &Path,
    env_vars: &BTreeMap<String, String>,
) -> Result<Checkout, CurupiraError> {
    if is_git_checkout(destination) {
        return Ok(Checkout {
            path: destination.to_path_buf(),
            cloned: false,
        });
    }
    if destination.exists() {
        return Err(CurupiraError::Dispatch(format!(
            "workspace destination exists but is not a Git checkout: {}",
            destination.display()
        )));
    }
    if let Some(parent) = destination.parent() {
        std::fs::create_dir_all(parent).map_err(|e| {
            CurupiraError::Dispatch(format!(
                "cannot create workspace directory {}: {e}",
                parent.display()
            ))
        })?;
    }
    match clone_repo(remote, destination, env_vars).await {
        Ok(()) => {
            if !is_git_checkout(destination) {
                let _ = remove_tree(destination);
                return Err(CurupiraError::Dispatch(format!(
                    "clone reported success, but no Git checkout was created at {}",
                    destination.display()
                )));
            }
            Ok(Checkout {
                path: destination.to_path_buf(),
                cloned: true,
            })
        }
        Err(err) => {
            let _ = remove_tree(destination);
            Err(err)
        }
    }
}

async fn clone_repo(
    remote: &str,
    dest: &Path,
    env_vars: &BTreeMap<String, String>,
) -> Result<(), CurupiraError> {
    let args = vec![
        "clone".into(),
        remote.into(),
        dest.to_string_lossy().into_owned(),
    ];
    let result = run_process(
        "git",
        &args,
        None,
        &[],
        env_vars,
        Duration::from_secs(600),
        1_000_000,
    )
    .await
    .map_err(CurupiraError::Dispatch)?;
    if result.exit_code != 0 {
        return Err(CurupiraError::Dispatch(format!(
            "git clone failed: {}",
            String::from_utf8_lossy(&result.stderr)
        )));
    }
    Ok(())
}

fn sanitize_path_component(value: &str) -> String {
    value.replace('/', "-")
}

async fn ensure_worktree(
    base: &Path,
    automation_id: &str,
    task_type: &str,
    task_id: &str,
    env_vars: &BTreeMap<String, String>,
) -> Result<WorktreeHandle, CurupiraError> {
    let safe_task_id = hex_encode(Sha256::digest(task_id.as_bytes()));
    let safe_task_type = sanitize_path_component(task_type);
    let base_name = base
        .file_name()
        .map(|s| s.to_string_lossy().into_owned())
        .unwrap_or_else(|| "repo".into());
    let target = base
        .with_file_name(format!("{base_name}.worktrees"))
        .join(automation_id)
        .join(format!("{safe_task_type}-{safe_task_id}"));
    let branch = format!("curupira/{automation_id}/{safe_task_type}-{safe_task_id}");

    if target.is_dir() {
        return Ok(WorktreeHandle {
            path: target,
            branch,
            base: base.to_path_buf(),
        });
    }

    git_ok(
        base,
        &["fetch".into(), "origin".into()],
        "git fetch",
        env_vars,
    )
    .await?;
    let default_ref = git_stdout(
        base,
        &["symbolic-ref".into(), "refs/remotes/origin/HEAD".into()],
        "git symbolic-ref",
        env_vars,
    )
    .await?;
    if let Some(parent) = target.parent() {
        std::fs::create_dir_all(parent).map_err(|e| CurupiraError::Dispatch(e.to_string()))?;
    }
    git_ok(
        base,
        &[
            "worktree".into(),
            "add".into(),
            "-b".into(),
            branch.clone(),
            target.to_string_lossy().into_owned(),
            default_ref,
        ],
        "git worktree add",
        env_vars,
    )
    .await?;
    Ok(WorktreeHandle {
        path: target,
        branch,
        base: base.to_path_buf(),
    })
}

async fn remove_worktree(
    base: &Path,
    worktree: &WorktreeHandle,
    env_vars: &BTreeMap<String, String>,
) -> Result<(), CurupiraError> {
    git_ok(
        base,
        &[
            "worktree".into(),
            "remove".into(),
            "--force".into(),
            worktree.path.to_string_lossy().into_owned(),
        ],
        "git worktree remove",
        env_vars,
    )
    .await?;
    git_ok(
        base,
        &["branch".into(), "-D".into(), worktree.branch.clone()],
        "git branch",
        env_vars,
    )
    .await?;
    Ok(())
}

async fn run_setup_script(
    checkout: &Path,
    script: &str,
    settings: &ApplicationSettings,
) -> Result<(), CurupiraError> {
    let path = checkout.join(script);
    let timeout = Duration::from_secs(u64::from(settings.settings.task_timeout_minutes) * 60);
    let result = run_process(
        &path.to_string_lossy(),
        &[],
        Some(checkout),
        &[],
        &settings.environment.vars,
        timeout,
        settings.settings.max_output_bytes as usize,
    )
    .await
    .map_err(|e| {
        let _ = remove_tree(checkout);
        CurupiraError::Dispatch(format!("setup_script failed to start: {e}"))
    })?;
    if result.exit_code != 0 {
        let _ = remove_tree(checkout);
        return Err(CurupiraError::Dispatch(format!(
            "setup_script exited {}: {}",
            result.exit_code,
            String::from_utf8_lossy(&result.stderr)
        )));
    }
    Ok(())
}

async fn git_ok(
    cwd: &Path,
    args: &[String],
    label: &str,
    env_vars: &BTreeMap<String, String>,
) -> Result<(), CurupiraError> {
    let result = run_process(
        "git",
        args,
        Some(cwd),
        &[],
        env_vars,
        Duration::from_secs(600),
        1_000_000,
    )
    .await
    .map_err(CurupiraError::Dispatch)?;
    if result.exit_code != 0 {
        return Err(CurupiraError::Dispatch(format!(
            "{label} failed: {}",
            String::from_utf8_lossy(&result.stderr)
        )));
    }
    Ok(())
}

async fn git_stdout(
    cwd: &Path,
    args: &[String],
    label: &str,
    env_vars: &BTreeMap<String, String>,
) -> Result<String, CurupiraError> {
    let result = run_process(
        "git",
        args,
        Some(cwd),
        &[],
        env_vars,
        Duration::from_secs(120),
        1_000_000,
    )
    .await
    .map_err(CurupiraError::Dispatch)?;
    if result.exit_code != 0 {
        return Err(CurupiraError::Dispatch(format!(
            "{label} failed: {}",
            String::from_utf8_lossy(&result.stderr)
        )));
    }
    Ok(String::from_utf8_lossy(&result.stdout).trim().to_string())
}

fn is_git_checkout(path: &Path) -> bool {
    path.is_dir() && path.join(".git").exists()
}

fn remove_tree(path: &Path) -> Result<(), std::io::Error> {
    if path.exists() {
        std::fs::remove_dir_all(path)?;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::{
        AgentDefaults, AgentProfile, AgentsSettings, ApplicationSettings, ExecutionSettings,
        TaskIdentity,
    };
    use std::collections::BTreeMap;
    use std::process::Command;
    use tempfile::tempdir;

    fn minimal_settings(workspace: &Path) -> ApplicationSettings {
        ApplicationSettings {
            settings: ExecutionSettings {
                workspace_dir: workspace.to_string_lossy().into_owned(),
                ..ExecutionSettings::default()
            },
            repositories: BTreeMap::new(),
            agents: AgentsSettings {
                defaults: AgentDefaults {
                    profile: "p".into(),
                    timezone: "UTC".into(),
                },
                profiles: BTreeMap::from([(
                    "p".into(),
                    AgentProfile {
                        provider: "opencode".into(),
                        extra: serde_json::Map::new(),
                    },
                )]),
            },
            plugins: BTreeMap::new(),
            automations: BTreeMap::new(),
            assistant: Default::default(),
            environment: Default::default(),
        }
    }

    fn make_task(alias: &str, remote: &str, checkout: &str) -> Task {
        Task {
            identity: TaskIdentity {
                automation_id: "auto1".into(),
                repo: "owner/repo".into(),
                task_type: "cron".into(),
                id: "task-1".into(),
            },
            automation_id: "auto1".into(),
            values: Vec::new(),
            scheduled_for: None,
            prompt: "p".into(),
            trigger_type: "cron".into(),
            profile_name: "p".into(),
            provider: "opencode".into(),
            repository_remote: remote.into(),
            repository_alias: alias.into(),
            repository_path: None,
            setup_script: None,
            checkout: checkout.into(),
            workspace_dir: String::new(),
        }
    }

    fn init_bare_origin(dir: &Path) -> PathBuf {
        let origin = dir.join("origin.git");
        assert!(Command::new("git")
            .args(["init", "--bare", origin.to_str().unwrap()])
            .status()
            .unwrap()
            .success());
        let seed = dir.join("seed");
        assert!(Command::new("git")
            .args(["clone", origin.to_str().unwrap(), seed.to_str().unwrap()])
            .status()
            .unwrap()
            .success());
        std::fs::write(seed.join("README"), "hi").unwrap();
        assert!(Command::new("git")
            .args(["-C", seed.to_str().unwrap(), "add", "."])
            .status()
            .unwrap()
            .success());
        assert!(Command::new("git")
            .args([
                "-C",
                seed.to_str().unwrap(),
                "-c",
                "user.email=t@t",
                "-c",
                "user.name=t",
                "commit",
                "-m",
                "init"
            ])
            .status()
            .unwrap()
            .success());
        assert!(Command::new("git")
            .args(["-C", seed.to_str().unwrap(), "branch", "-M", "main"])
            .status()
            .unwrap()
            .success());
        assert!(Command::new("git")
            .args(["-C", seed.to_str().unwrap(), "push", "-u", "origin", "main"])
            .status()
            .unwrap()
            .success());
        // Ensure origin/HEAD exists for symbolic-ref
        assert!(Command::new("git")
            .args([
                "-C",
                origin.to_str().unwrap(),
                "symbolic-ref",
                "HEAD",
                "refs/heads/main"
            ])
            .status()
            .unwrap()
            .success());
        origin
    }

    #[tokio::test]
    async fn clone_reuse_and_worktree() {
        let tmp = tempdir().unwrap();
        let origin = init_bare_origin(tmp.path());
        let workspace = tmp.path().join("ws");
        let settings = minimal_settings(&workspace);
        let vcs = VersionControl::new();
        let task = make_task("demo", origin.to_str().unwrap(), "worktree");

        let prepared = vcs.prepare(&settings, &task).await.unwrap();
        assert!(prepared.base_checkout.join(".git").exists());
        assert!(prepared.worktree.is_some());
        assert!(prepared.cwd.join("README").exists());

        // Reuse base checkout
        let prepared2 = vcs.prepare(&settings, &task).await.unwrap();
        assert_eq!(prepared.base_checkout, prepared2.base_checkout);

        vcs.cleanup(&settings.environment.vars, &prepared)
            .await
            .unwrap();
        assert!(!prepared.cwd.exists());
    }

    #[tokio::test]
    async fn shared_main_checkout_no_worktree() {
        let tmp = tempdir().unwrap();
        let origin = init_bare_origin(tmp.path());
        let workspace = tmp.path().join("ws");
        let settings = minimal_settings(&workspace);
        let vcs = VersionControl::new();
        let task = make_task("shared", origin.to_str().unwrap(), "main");
        let prepared = vcs.prepare(&settings, &task).await.unwrap();
        assert!(prepared.worktree.is_none());
        assert_eq!(prepared.cwd, prepared.base_checkout);
        // second prepare reuses without error
        let again = vcs.prepare(&settings, &task).await.unwrap();
        assert_eq!(again.cwd, prepared.cwd);
    }
}
