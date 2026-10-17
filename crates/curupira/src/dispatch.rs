//! Task discovery, scheduling admission, and coding-agent execution.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use chrono::Utc;
use serde_json::json;

use crate::config::{
    expand_user, resolve_automations, ApplicationSettings, ResolvedAutomation, Task,
};
use crate::cron;
use crate::error::CurupiraError;
use crate::extensions::host::ExtensionHost;
use crate::extensions::registry::ExtensionRegistry;
use crate::process::run_process;
use crate::storage::{open_db, CompletedTaskRepository, CronScheduleRepository};

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
    let registry = ExtensionRegistry::load()?;

    if dry_run {
        let tasks = poll_all(settings, &automations, &conn, &registry, true).await?;
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

    let mut failed = 0_u32;
    let mut admitted = 0_u32;
    let max_active = settings.settings.max_active_tasks.max(1);

    loop {
        if interrupted.load(Ordering::SeqCst) {
            break;
        }
        let tasks = poll_all(settings, &automations, &conn, &registry, false).await?;
        if tasks.is_empty() {
            if !watch {
                break;
            }
            tokio::time::sleep(Duration::from_secs(
                settings.settings.polling.poll_interval_seconds.max(1),
            ))
            .await;
            continue;
        }

        let completed = CompletedTaskRepository::new(&conn);
        let mut batch = Vec::new();
        for task in tasks {
            if size.is_some_and(|n| admitted >= n) {
                break;
            }
            if completed.contains(&task.identity.key())? {
                continue;
            }
            batch.push(task);
            if batch.len() as u32 >= max_active {
                break;
            }
        }

        if batch.is_empty() {
            if !watch {
                break;
            }
            tokio::time::sleep(Duration::from_secs(
                settings.settings.polling.poll_interval_seconds.max(1),
            ))
            .await;
            continue;
        }

        for task in batch {
            if interrupted.load(Ordering::SeqCst) {
                break;
            }
            admitted += 1;
            match execute_task(settings, &task, &conn, &registry).await {
                Ok(()) => {
                    completed.mark(&task.identity.key(), Utc::now())?;
                    println!("ok\t{}\t{}", task.identity.key(), task.title);
                }
                Err(err) => {
                    failed += 1;
                    eprintln!("fail\t{}\t{err}", task.identity.key());
                }
            }
            if size.is_some_and(|n| admitted >= n) {
                break;
            }
        }

        if !watch || size.is_some_and(|n| admitted >= n) {
            break;
        }
    }

    if failed > 0 {
        return Err(CurupiraError::Dispatch(format!("{failed} task(s) failed")));
    }
    Ok(())
}

async fn poll_all(
    settings: &ApplicationSettings,
    automations: &[ResolvedAutomation],
    conn: &rusqlite::Connection,
    registry: &ExtensionRegistry,
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

        let ext_name = registry
            .extension_for_trigger(&automation.trigger_type)
            .ok_or_else(|| {
                CurupiraError::Plugin(format!(
                    "no extension for trigger {}",
                    automation.trigger_type
                ))
            })?
            .to_string();
        let host = if let Some(h) = hosts.get_mut(&ext_name) {
            h
        } else {
            let installed = registry
                .get(&ext_name)
                .ok_or_else(|| CurupiraError::Plugin(format!("missing extension {ext_name}")))?;
            let host = ExtensionHost::spawn(installed)?;
            hosts.insert(ext_name.clone(), host);
            hosts.get_mut(&ext_name).unwrap()
        };

        let batch_size = settings.settings.polling.batch_size.max(1);
        for _ in 0..batch_size {
            let result = host.poll_trigger(
                &automation.trigger_type,
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
    registry: &ExtensionRegistry,
) -> Result<(), CurupiraError> {
    let work_dir = checkout_workspace(settings, task).await?;

    if task.trigger_type == "cron" {
        let repo = CronScheduleRepository::new(conn);
        cron::on_task_started(&repo, task)?;
    } else if let Some(ext_name) = registry.extension_for_trigger(&task.trigger_type) {
        let installed = registry.get(ext_name).unwrap();
        let mut host = ExtensionHost::spawn(installed)?;
        let task_json =
            serde_json::to_value(task).map_err(|e| CurupiraError::Plugin(e.to_string()))?;
        host.on_started(&task.trigger_type, &task_json)?;
        host.shutdown()?;
    }

    let result = run_agent(settings, task, &work_dir, registry).await;

    if task.trigger_type == "cron" {
        let repo = CronScheduleRepository::new(conn);
        cron::on_task_finished(&repo, task)?;
    } else if let Some(ext_name) = registry.extension_for_trigger(&task.trigger_type) {
        let installed = registry.get(ext_name).unwrap();
        let mut host = ExtensionHost::spawn(installed)?;
        let task_json =
            serde_json::to_value(task).map_err(|e| CurupiraError::Plugin(e.to_string()))?;
        let _ = host.on_finished(&task.trigger_type, &task_json);
        let _ = host.shutdown();
    }

    result
}

async fn checkout_workspace(
    settings: &ApplicationSettings,
    task: &Task,
) -> Result<PathBuf, CurupiraError> {
    let root = expand_user(&settings.settings.workspace_dir);
    std::fs::create_dir_all(&root).map_err(|e| CurupiraError::Dispatch(e.to_string()))?;
    let dest = root.join(format!(
        "{}-{}",
        task.automation_id,
        &task.identity.id[..task.identity.id.len().min(12)]
    ));
    if task.checkout == "main" {
        // Shared checkout: reuse a stable directory per repo identity.
        let shared = root.join(task.identity.repo.replace('/', "_"));
        if !shared.join(".git").exists() {
            clone_repo(&task.repository_remote, &shared).await?;
        }
        return Ok(shared);
    }
    if dest.exists() {
        let _ = std::fs::remove_dir_all(&dest);
    }
    clone_repo(&task.repository_remote, &dest).await?;
    Ok(dest)
}

async fn clone_repo(remote: &str, dest: &Path) -> Result<(), CurupiraError> {
    let args = vec![
        "clone".into(),
        "--depth".into(),
        "1".into(),
        remote.into(),
        dest.to_string_lossy().into_owned(),
    ];
    let result = run_process("git", &args, None, &[], Duration::from_secs(300), 1_000_000)
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

async fn run_agent(
    settings: &ApplicationSettings,
    task: &Task,
    work_dir: &Path,
    registry: &ExtensionRegistry,
) -> Result<(), CurupiraError> {
    let profile = settings
        .agents
        .profiles
        .get(&task.profile_name)
        .ok_or_else(|| CurupiraError::Dispatch(format!("missing profile {}", task.profile_name)))?;

    let mut profile_json =
        serde_json::to_value(profile).map_err(|e| CurupiraError::Dispatch(e.to_string()))?;
    if let Some(obj) = profile_json.as_object_mut() {
        obj.insert("provider".into(), json!(profile.provider));
    }

    let request = json!({
        "prompt": task.prompt,
        "cwd": work_dir,
        "task": task,
    });

    let ext_name = registry
        .extension_for_agent(&task.provider)
        .ok_or_else(|| {
            CurupiraError::Plugin(format!(
                "no installed extension provides coding-agent provider {:?}",
                task.provider
            ))
        })?;
    let installed = registry
        .get(ext_name)
        .ok_or_else(|| CurupiraError::Plugin(format!("missing extension {ext_name}")))?;
    let mut host = ExtensionHost::spawn(installed)?;
    let built = host.build_arguments(&task.provider, &profile_json, &request)?;
    host.shutdown()?;

    if built.argv.is_empty() {
        return Err(CurupiraError::Plugin("agent returned empty argv".into()));
    }
    let program = built.argv[0].clone();
    let args = built.argv[1..].to_vec();
    let timeout = Duration::from_secs(u64::from(settings.settings.task_timeout_minutes) * 60);
    let result = run_process(
        &program,
        &args,
        Some(work_dir),
        &built.env,
        timeout,
        settings.settings.max_output_bytes as usize,
    )
    .await
    .map_err(CurupiraError::Dispatch)?;
    if result.exit_code != 0 {
        return Err(CurupiraError::Dispatch(format!(
            "agent exited {}: {}",
            result.exit_code,
            String::from_utf8_lossy(&result.stderr)
        )));
    }
    Ok(())
}
