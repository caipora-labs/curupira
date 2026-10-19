//! Task discovery, scheduling admission, and coding-agent execution.

use std::collections::{BTreeMap, HashSet};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Duration;

use chrono::Utc;
use futures::stream::{FuturesUnordered, StreamExt};
use sha2::{Digest, Sha256};
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
use crate::protocol::KeyValue;
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
    let namespace = PluginNamespaceIndex::build(&settings.plugins, &settings.environment.vars)?;

    if dry_run {
        let tasks = poll_all(settings, &automations, &conn, &namespace, true).await?;
        if let Some(task) = tasks.into_iter().next() {
            println!("dry-run\t{}", task.identity.key());
            // The rendered prompt is what the agent would receive: check templates here.
            println!(
                "--- prompt ---\n{}\n--- end prompt ---",
                task.prompt.trim_end()
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
        let TaskOutcome { key, result } = outcome;
        in_flight.remove(&key);
        match result {
            Ok(()) => {
                completed.mark(&key, Utc::now())?;
                println!("ok\t{key}");
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
    let result = execute_task(settings, &task, conn, vcs, namespace).await;
    TaskOutcome { key, result }
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
            let host = ExtensionHost::spawn_plugin(
                &binding.alias,
                &binding.launch,
                &settings.environment.vars,
            )?;
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
            match result.values {
                None => break,
                Some(values) => {
                    tasks.push(task_from_values(settings, automation, values)?);
                }
            }
        }
    }

    for (_, mut host) in hosts {
        let _ = host.shutdown();
    }
    Ok(tasks)
}

fn task_from_values(
    settings: &ApplicationSettings,
    automation: &ResolvedAutomation,
    values: Vec<KeyValue>,
) -> Result<Task, CurupiraError> {
    let prompt = render_prompt(
        &automation.prompt,
        &values,
        &automation.identity_repo,
        &automation.automation_id,
    )?;
    let id = content_id(&values);
    Ok(Task {
        identity: crate::config::TaskIdentity {
            automation_id: automation.automation_id.clone(),
            repo: automation.identity_repo.clone(),
            task_type: automation.trigger_type.clone(),
            id,
        },
        automation_id: automation.automation_id.clone(),
        values,
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

/// Stable identity for a trigger result. Order is significant; no field is injected.
fn content_id(values: &[KeyValue]) -> String {
    let canonical = serde_json::to_string(values).expect("key-value list is JSON");
    hex::encode(Sha256::digest(canonical.as_bytes()))
}

fn validate_pairs(values: &[KeyValue]) -> Result<(), CurupiraError> {
    let mut seen = HashSet::new();
    for pair in values {
        if pair.key.is_empty() || pair.key.contains('}') || pair.key.contains("${") {
            return Err(CurupiraError::Plugin(format!(
                "trigger result key {:?} cannot be used as a template placeholder",
                pair.key
            )));
        }
        if pair.key == "repository" || pair.key == "automation" {
            return Err(CurupiraError::Plugin(format!(
                "trigger result key {:?} collides with a host template variable",
                pair.key
            )));
        }
        if !seen.insert(pair.key.clone()) {
            return Err(CurupiraError::Plugin(format!(
                "trigger result has duplicate key {:?}",
                pair.key
            )));
        }
    }
    Ok(())
}

/// Render a prompt: `${key}` substitution and Jinja. Inserted text is never scanned again.
///
/// `${repository}` and `${automation}` come from the automation, not the trigger
/// result. A placeholder with no match is left unchanged.
pub(crate) fn render_prompt(
    template: &str,
    values: &[KeyValue],
    repository: &str,
    automation_id: &str,
) -> Result<String, CurupiraError> {
    validate_pairs(values)?;
    crate::prompt::render(template, values, repository, automation_id)
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
        let mut host = ExtensionHost::spawn_plugin(
            &binding.alias,
            &binding.launch,
            &settings.environment.vars,
        )?;
        host.on_started(&binding.local_trigger, &task.values)?;
        host.shutdown()?;
    }

    let result = run_agent(settings, task, &prepared.cwd, conn).await;

    if task.trigger_type == "cron" {
        let repo = CronScheduleRepository::new(conn);
        cron::on_task_finished(&repo, task)?;
    } else if let Some(binding) = namespace.resolve(&task.trigger_type) {
        let mut host = ExtensionHost::spawn_plugin(
            &binding.alias,
            &binding.launch,
            &settings.environment.vars,
        )?;
        let _ = host.on_finished(&binding.local_trigger, &task.values);
        let _ = host.shutdown();
    }

    if let Err(err) = vcs.cleanup(&settings.environment.vars, &prepared).await {
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

    if crate::process::resolve_executable(&launch.program).is_err() {
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
        &settings.environment.vars,
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

#[cfg(test)]
mod tests {
    use std::collections::BTreeMap;

    use super::*;
    use crate::config::{
        AgentDefaults, AgentProfile, AgentsSettings, ApplicationSettings, ExecutionSettings,
        RepositoryConfiguration, ResolvedAutomation,
    };

    fn pair(key: &str, value: &str) -> KeyValue {
        KeyValue {
            key: key.into(),
            value: value.into(),
        }
    }

    fn settings() -> ApplicationSettings {
        ApplicationSettings {
            settings: ExecutionSettings::default(),
            repositories: BTreeMap::new(),
            agents: AgentsSettings {
                defaults: AgentDefaults {
                    profile: "p".into(),
                    timezone: "UTC".into(),
                },
                profiles: BTreeMap::new(),
            },
            plugins: BTreeMap::new(),
            automations: BTreeMap::new(),
            assistant: Default::default(),
            environment: Default::default(),
        }
    }

    fn automation(prompt: &str) -> ResolvedAutomation {
        ResolvedAutomation {
            automation_id: "weekly".into(),
            identity_repo: "acme/api".into(),
            repository_alias: "api".into(),
            configuration: serde_json::json!({}),
            trigger_type: "plugins-py/example".into(),
            repository: RepositoryConfiguration {
                remote: "https://example.test/acme/api.git".into(),
                path: None,
                setup_script: None,
            },
            profile: AgentProfile {
                provider: "opencode".into(),
                extra: serde_json::Map::new(),
            },
            profile_name: "p".into(),
            prompt: prompt.into(),
            checkout: "worktree".into(),
        }
    }

    #[test]
    fn interpolates_generic_keys_including_non_identifiers() {
        let rendered = render_prompt(
            "n=${issue-number} dot=${foo.bar} num=${123} spaced=${a b} host=${repository}/${automation}",
            &[
                pair("issue-number", "42"),
                pair("foo.bar", "x"),
                pair("123", "n"),
                pair("a b", "s"),
            ],
            "acme/api",
            "weekly",
        )
        .unwrap();
        assert_eq!(rendered, "n=42 dot=x num=n spaced=s host=acme/api/weekly");
    }

    #[test]
    fn missing_placeholder_stays_and_values_are_not_reexpanded() {
        let rendered = render_prompt(
            "keep ${missing}; value=${name}; bare ${",
            &[pair("name", "${other}"), pair("other", "nope")],
            "acme/api",
            "weekly",
        )
        .unwrap();
        assert_eq!(rendered, "keep ${missing}; value=${other}; bare ${");
    }

    #[test]
    fn rejects_duplicate_reserved_and_unaddressable_keys() {
        let err = render_prompt("x", &[pair("a", "1"), pair("a", "2")], "r", "a").unwrap_err();
        assert!(err.to_string().contains("duplicate"));
        let err = render_prompt("x", &[pair("repository", "1")], "r", "a").unwrap_err();
        assert!(err.to_string().contains("collides"));
        let err = render_prompt("x", &[pair("automation", "1")], "r", "a").unwrap_err();
        assert!(err.to_string().contains("collides"));
        let err = render_prompt("x", &[pair("a}", "1")], "r", "a").unwrap_err();
        assert!(err.to_string().contains("placeholder"));
        let err = render_prompt("x", &[pair("${a", "1")], "r", "a").unwrap_err();
        assert!(err.to_string().contains("placeholder"));
        let err = render_prompt("x", &[pair("", "1")], "r", "a").unwrap_err();
        assert!(err.to_string().contains("placeholder"));
    }

    #[test]
    fn content_id_is_stable_and_order_sensitive() {
        let first = vec![pair("b", "1"), pair("a", "2")];
        let same = vec![pair("b", "1"), pair("a", "2")];
        let swapped = vec![pair("a", "2"), pair("b", "1")];
        assert_eq!(content_id(&first), content_id(&same));
        assert_ne!(content_id(&first), content_id(&swapped));
        assert_eq!(content_id(&[]), hex::encode(Sha256::digest(b"[]")));
        let canonical = serde_json::to_string(&first).unwrap();
        assert_eq!(
            canonical,
            r#"[{"key":"b","value":"1"},{"key":"a","value":"2"}]"#
        );
    }

    #[test]
    fn empty_list_is_a_task_without_provider_fields() {
        let task =
            task_from_values(&settings(), &automation("see ${note} ${missing}"), vec![]).unwrap();
        assert!(task.values.is_empty());
        assert_eq!(task.prompt, "see ${note} ${missing}");
        assert_eq!(task.identity.id, content_id(&[]));
        assert!(!task.identity.key().contains("title"));

        let task = task_from_values(
            &settings(),
            &automation("${issue-number}"),
            vec![pair("issue-number", "7")],
        )
        .unwrap();
        assert_eq!(task.prompt, "7");
        assert_eq!(task.values.len(), 1);
        assert_eq!(task.identity.id, content_id(&task.values));
    }
}
