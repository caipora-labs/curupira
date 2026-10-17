//! Task discovery, scheduling admission, and coding-agent execution.

use std::collections::{BTreeMap, HashSet};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use chrono::Utc;
use futures::stream::{FuturesUnordered, StreamExt};
use serde_json::json;
use uuid::Uuid;

use crate::agents::{self, AgentProvider, AgentRequest};
use crate::config::{
    expand_user, resolve_automations, ApplicationSettings, ResolvedAutomation, Task,
};
use crate::cron;
use crate::error::CurupiraError;
use crate::extensions::host::ExtensionHost;
use crate::extensions::namespace::PluginNamespaceIndex;
use crate::process::run_process;
use crate::storage::{
    open_db, CompletedTaskRepository, CronScheduleRepository, RunningCodingSession,
    RunningSessionRepository,
};
use crate::vcs::VersionControl;

/// Run `run` / watch / dry-run after settings are loaded.
pub async fn run_command(
    settings: &ApplicationSettings,
    dry_run: bool,
    watch: bool,
    size: Option<u32>,
    interrupted: &AtomicBool,
) -> Result<(), CurupiraError> {
    let automations = resolve_automations(settings)?;
    let db_path = expand_user(&settings.settings.state_db_path);
    let conn = open_db(&db_path)?;
    let namespace = PluginNamespaceIndex::build(&settings.plugins)?;

    if dry_run {
        let tasks = poll_all(settings, &automations, &conn, &namespace, true).await?;
        if let Some(task) = tasks.into_iter().next() {
            println!(
                "dry-run\t{}\t{}\t{}",
                task.identity.key(),
                task.title,
                task.url
            );
        } else {
            println!("dry-run\t(no tasks available)");
        }
        return Ok(());
    }

    // One VersionControl for the whole run: its per-checkout locks must be shared by every worker.
    let vcs = VersionControl::new();
    let completed = CompletedTaskRepository::new(&conn);
    let poll_interval = Duration::from_secs(settings.settings.polling.poll_interval_seconds.max(1));
    let workers = settings.settings.max_active_tasks.max(1) as usize;

    let mut running = FuturesUnordered::new();
    let mut in_flight: HashSet<String> = HashSet::new();
    // Every task admitted in this run, so a failed task is not re-run in a loop.
    let mut attempted: HashSet<String> = HashSet::new();
    let mut admitted = 0_u32;
    let mut failed = 0_u32;

    loop {
        // Fill free workers from a fresh poll; tasks already running or attempted are skipped.
        let mut exhausted = false;
        while !exhausted
            && running.len() < workers
            && !interrupted.load(Ordering::SeqCst)
            && size.is_none_or(|n| admitted < n)
        {
            let tasks = poll_all(settings, &automations, &conn, &namespace, false).await?;
            if tasks.is_empty() {
                exhausted = true;
            }
            for task in tasks {
                if running.len() >= workers || size.is_some_and(|n| admitted >= n) {
                    break;
                }
                let key = task.identity.key();
                if in_flight.contains(&key)
                    || attempted.contains(&key)
                    || completed.contains(&key)?
                {
                    continue;
                }
                admitted += 1;
                in_flight.insert(key.clone());
                attempted.insert(key);
                running.push(run_task(settings, task, &conn, &vcs, &namespace));
            }
            if running.len() < workers {
                exhausted = true;
            }
        }

        if running.is_empty() {
            let stop =
                !watch || interrupted.load(Ordering::SeqCst) || size.is_some_and(|n| admitted >= n);
            if stop {
                break;
            }
            tokio::time::sleep(poll_interval).await;
            continue;
        }

        // Wait for a worker to finish. In watch mode, wake up periodically to poll for new tasks.
        let next = if watch {
            tokio::time::timeout(poll_interval, running.next())
                .await
                .ok()
                .flatten()
        } else {
            running.next().await
        };
        let Some(outcome) = next else { continue };
        let TaskOutcome { key, title, result } = outcome;
        in_flight.remove(&key);
        match result {
            Ok(()) => {
                completed.mark(&key, Utc::now())?;
                println!("ok\t{key}\t{title}");
            }
            Err(err) => {
                failed += 1;
                eprintln!("fail\t{key}\t{err}");
            }
        }
    }

    if failed > 0 {
        return Err(CurupiraError::Dispatch(format!("{failed} task(s) failed")));
    }
    Ok(())
}

/// Result of one worker, returned to the dispatch loop when it finishes.
struct TaskOutcome {
    key: String,
    title: String,
    result: Result<(), CurupiraError>,
}

async fn run_task(
    settings: &ApplicationSettings,
    task: Task,
    conn: &rusqlite::Connection,
    vcs: &VersionControl,
    namespace: &PluginNamespaceIndex,
) -> TaskOutcome {
    let key = task.identity.key();
    let title = task.title.clone();
    let result = execute_task(settings, &task, conn, vcs, namespace).await;
    TaskOutcome { key, title, result }
}

async fn poll_all(
    settings: &ApplicationSettings,
    automations: &[ResolvedAutomation],
    conn: &rusqlite::Connection,
    namespace: &PluginNamespaceIndex,
    preview: bool,
) -> Result<Vec<Task>, CurupiraError> {
    let mut tasks = Vec::new();
    let cron_repo = CronScheduleRepository::new(conn);
    let mut hosts: BTreeMap<String, ExtensionHost> = BTreeMap::new();

    for automation in automations {
        if automation.trigger_type == "cron" {
            let mut found = cron::poll_cron(
                automation,
                &cron_repo,
                preview,
                Utc::now(),
                &settings.settings.workspace_dir,
            )?;
            tasks.append(&mut found);
            continue;
        }

        let binding = namespace.resolve(&automation.trigger_type).ok_or_else(|| {
            CurupiraError::Plugin(format!(
                "no extension for trigger {}",
                automation.trigger_type
            ))
        })?;
        let cache_key = binding.alias.clone();
        let local_trigger = binding.local_trigger.clone();
        let host = if let Some(h) = hosts.get_mut(&cache_key) {
            h
        } else {
            let host = ExtensionHost::spawn_plugin(&binding.alias, &binding.launch)?;
            hosts.insert(cache_key.clone(), host);
            hosts.get_mut(&cache_key).unwrap()
        };

        let batch_size = settings.settings.polling.batch_size.max(1);
        for _ in 0..batch_size {
            let result = host.poll_trigger(
                &local_trigger,
                &automation.configuration,
                preview,
                batch_size,
            )?;
            match result.task {
                None => break,
                Some(value) => {
                    tasks.push(task_from_extension_value(settings, automation, value)?);
                }
            }
        }
    }

    for (_, mut host) in hosts {
        let _ = host.shutdown();
    }
    Ok(tasks)
}

fn task_from_extension_value(
    settings: &ApplicationSettings,
    automation: &ResolvedAutomation,
    value: serde_json::Value,
) -> Result<Task, CurupiraError> {
    let id = value
        .get("id")
        .and_then(|v| v.as_str())
        .ok_or_else(|| CurupiraError::Plugin("extension task missing id".into()))?
        .to_string();
    let title = value
        .get("title")
        .and_then(|v| v.as_str())
        .unwrap_or(&id)
        .to_string();
    let url = value
        .get("url")
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();
    let item = value.get("item").cloned().unwrap_or_else(|| json!({}));
    let prompt = render_template(&automation.prompt, &item, automation);
    Ok(Task {
        identity: crate::config::TaskIdentity {
            automation_id: automation.automation_id.clone(),
            repo: automation.identity_repo.clone(),
            task_type: automation.trigger_type.clone(),
            id,
        },
        automation_id: automation.automation_id.clone(),
        title,
        url,
        item,
        scheduled_for: None,
        prompt,
        trigger_type: automation.trigger_type.clone(),
        profile_name: automation.profile_name.clone(),
        provider: automation.profile.provider.clone(),
        repository_remote: automation.repository.remote.clone(),
        repository_alias: automation.repository_alias.clone(),
        repository_path: automation.repository.path.clone(),
        setup_script: automation.repository.setup_script.clone(),
        checkout: automation.checkout.clone(),
        workspace_dir: expand_user(&settings.settings.workspace_dir)
            .to_string_lossy()
            .into_owned(),
    })
}

fn render_template(
    template: &str,
    item: &serde_json::Value,
    automation: &ResolvedAutomation,
) -> String {
    let mut out = template
        .replace("${repository}", &automation.identity_repo)
        .replace("${automation}", &automation.automation_id);
    if let Some(obj) = item.as_object() {
        for (k, v) in obj {
            let needle = format!("${{{k}}}");
            let value = match v {
                serde_json::Value::String(s) => s.clone(),
                other => other.to_string(),
            };
            out = out.replace(&needle, &value);
        }
    }
    out
}

async fn execute_task(
    settings: &ApplicationSettings,
    task: &Task,
    conn: &rusqlite::Connection,
    vcs: &VersionControl,
    namespace: &PluginNamespaceIndex,
) -> Result<(), CurupiraError> {
    let prepared = vcs.prepare(settings, task).await?;

    if task.trigger_type == "cron" {
        let repo = CronScheduleRepository::new(conn);
        cron::on_task_started(&repo, task)?;
    } else if let Some(binding) = namespace.resolve(&task.trigger_type) {
        let mut host = ExtensionHost::spawn_plugin(&binding.alias, &binding.launch)?;
        let task_json =
            serde_json::to_value(task).map_err(|e| CurupiraError::Plugin(e.to_string()))?;
        host.on_started(&binding.local_trigger, &task_json)?;
        host.shutdown()?;
    }

    let result = run_agent(settings, task, &prepared.cwd, conn).await;

    if task.trigger_type == "cron" {
        let repo = CronScheduleRepository::new(conn);
        cron::on_task_finished(&repo, task)?;
    } else if let Some(binding) = namespace.resolve(&task.trigger_type) {
        let mut host = ExtensionHost::spawn_plugin(&binding.alias, &binding.launch)?;
        let task_json =
            serde_json::to_value(task).map_err(|e| CurupiraError::Plugin(e.to_string()))?;
        let _ = host.on_finished(&binding.local_trigger, &task_json);
        let _ = host.shutdown();
    }

    if let Err(err) = vcs.cleanup(&prepared).await {
        tracing::warn!("worktree cleanup failed: {err}");
    }

    if result.is_ok() {
        let sessions = RunningSessionRepository::new(conn);
        let _ = sessions.delete(&task.identity.key());
    }

    result
}

const RESUME_SESSION_PROMPT: &str =
    "Continue the previous coding task for this work item. Use the repository state and prior session context.";

async fn run_agent(
    settings: &ApplicationSettings,
    task: &Task,
    work_dir: &std::path::Path,
    conn: &rusqlite::Connection,
) -> Result<(), CurupiraError> {
    let profile = settings
        .agents
        .profiles
        .get(&task.profile_name)
        .ok_or_else(|| CurupiraError::Dispatch(format!("missing profile {}", task.profile_name)))?;
    let provider = AgentProvider::parse(&profile.provider)?;

    let sessions = RunningSessionRepository::new(conn);
    let existing = sessions.get(&task.identity.key())?;
    let (message, session_id, new_session_id) = if let Some(existing) = &existing {
        (
            RESUME_SESSION_PROMPT.to_string(),
            Some(existing.session_id.clone()),
            None,
        )
    } else if provider.assigns_session_id() {
        let id = Uuid::new_v4().to_string();
        sessions.save(
            &task.identity.key(),
            &RunningCodingSession {
                session_id: id.clone(),
                provider: provider.as_str().into(),
                original_prompt: task.prompt.clone(),
            },
        )?;
        (task.prompt.clone(), None, Some(id))
    } else {
        (task.prompt.clone(), None, None)
    };

    let request = AgentRequest {
        message,
        cwd: work_dir.to_path_buf(),
        session_id,
        new_session_id,
    };
    let launch = agents::build_headless(provider, profile, &request)?;

    if which::which(&launch.program).is_err() {
        return Err(CurupiraError::Dispatch(format!(
            "coding-agent executable {:?} not found on PATH (provider {})",
            launch.program,
            provider.as_str()
        )));
    }

    let timeout = Duration::from_secs(u64::from(settings.settings.task_timeout_minutes) * 60);
    let result = run_process(
        &launch.program,
        &launch.args,
        Some(work_dir),
        &launch.env,
        timeout,
        settings.settings.max_output_bytes as usize,
    )
    .await
    .map_err(CurupiraError::Dispatch)?;

    // Persist the first native session id announced on stdout (when not caller-assigned).
    if !provider.assigns_session_id() && existing.is_none() {
        let stdout = String::from_utf8_lossy(&result.stdout);
        for line in stdout.lines() {
            if let Some(id) = agents::session_id_from_line(provider, line) {
                let _ = sessions.save(
                    &task.identity.key(),
                    &RunningCodingSession {
                        session_id: id,
                        provider: provider.as_str().into(),
                        original_prompt: task.prompt.clone(),
                    },
                );
                break;
            }
        }
    }

    if result.exit_code != 0 {
        return Err(CurupiraError::Dispatch(format!(
            "agent exited {}: {}",
            result.exit_code,
            String::from_utf8_lossy(&result.stderr)
        )));
    }
    Ok(())
}
