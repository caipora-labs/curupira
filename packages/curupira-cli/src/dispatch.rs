//! Task discovery, scheduling admission, and coding-agent execution.

use std::collections::{BTreeMap, HashSet};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
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
use crate::process::{run_process, run_process_with_lines, LineSink};
use crate::protocol::KeyValue;
use crate::storage::{
    open_db, CronScheduleRepository, RunningCodingSession, RunningSessionRepository,
};
use crate::vcs::VersionControl;

/// A task the dispatch loop just admitted, described for display.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct TaskStart {
    pub key: String,
    pub automation: String,
    /// `#123 Title` for issues and pull requests; the automation id otherwise.
    pub title: String,
    pub url: Option<String>,
    /// Provider and model, e.g. `opencode · openai/gpt-5.5`.
    pub agent: String,
    pub prompt: String,
}

impl TaskStart {
    fn describe(settings: &ApplicationSettings, task: &Task) -> Self {
        let value = |name: &str| {
            task.values
                .iter()
                .find(|kv| kv.key == name)
                .map(|kv| kv.value.clone())
                .filter(|v| !v.is_empty())
        };
        let (title, url) = ["pull_request", "issue", "item"]
            .iter()
            .find_map(|kind| {
                let title = value(&format!("{kind}_title"))?;
                let title = match value(&format!("{kind}_number")) {
                    Some(number) => format!("#{number} {title}"),
                    None => title,
                };
                Some((title, value(&format!("{kind}_url"))))
            })
            .unwrap_or_else(|| (task.automation_id.clone(), None));
        let model = settings
            .agents
            .profiles
            .get(&task.profile_name)
            .and_then(|profile| profile.extra.get("model"))
            .and_then(serde_json::Value::as_str);
        let agent = match model {
            Some(model) => format!("{} · {model}", task.provider),
            None => task.provider.clone(),
        };
        Self {
            key: task.identity.key(),
            automation: task.automation_id.clone(),
            title,
            url,
            agent,
            prompt: task.prompt.clone(),
        }
    }
}

/// Progress of the dispatch loop, as reported to a [`Reporter`].
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum DispatchEvent {
    Started(TaskStart),
    /// One stdout line from the task's coding agent.
    Output {
        key: String,
        line: String,
    },
    /// The coding agent named its session (OpenCode generates a title after a few seconds).
    Titled {
        key: String,
        title: String,
    },
    Ok(String),
    Fail {
        key: String,
        error: String,
    },
}

/// Where dispatch progress goes: stdout/stderr for `run`, a callback for the TUI.
#[derive(Clone, Default)]
pub enum Reporter {
    #[default]
    Stdio,
    Callback(Arc<dyn Fn(DispatchEvent) + Send + Sync>),
}

impl std::fmt::Debug for Reporter {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(match self {
            Self::Stdio => "Reporter::Stdio",
            Self::Callback(_) => "Reporter::Callback",
        })
    }
}

impl Reporter {
    pub fn report(&self, event: DispatchEvent) {
        match self {
            Self::Stdio => match event {
                DispatchEvent::Started(_)
                | DispatchEvent::Output { .. }
                | DispatchEvent::Titled { .. } => {}
                DispatchEvent::Ok(key) => println!("ok\t{key}"),
                DispatchEvent::Fail { key, error } => eprintln!("fail\t{key}\t{error}"),
            },
            Self::Callback(callback) => callback(event),
        }
    }

    /// Forwards the agent's stdout lines for `key`; `run` does not print them.
    fn output_sink(&self, key: &str) -> Option<LineSink> {
        match self {
            Self::Stdio => None,
            Self::Callback(callback) => {
                let callback = Arc::clone(callback);
                let key = key.to_owned();
                Some(Arc::new(move |line| {
                    callback(DispatchEvent::Output {
                        key: key.clone(),
                        line,
                    });
                }))
            }
        }
    }
}

/// Tasks this process has dispatched, finished or not. Memory only: a new run starts empty, so
/// nothing runs twice while Curupira is running, yet no issue or pull request history is kept
/// across runs. Which items are due is decided by the trigger filters (labels, state, links).
#[derive(Debug, Default)]
struct Dispatched(HashSet<String>);

impl Dispatched {
    /// Record `key`; `false` when this process already dispatched it.
    fn first_time(&mut self, key: &str) -> bool {
        self.0.insert(key.to_owned())
    }
}

/// Sleep for `duration`, waking early once `interrupted` is set.
async fn sleep_unless_interrupted(duration: Duration, interrupted: &AtomicBool) {
    let step = Duration::from_millis(200);
    let deadline = tokio::time::Instant::now() + duration;
    while !interrupted.load(Ordering::SeqCst) {
        let now = tokio::time::Instant::now();
        if now >= deadline {
            break;
        }
        tokio::time::sleep(step.min(deadline - now)).await;
    }
}

/// Run `run` / watch / dry-run after settings are loaded.
pub async fn run_command(
    settings: &ApplicationSettings,
    dry_run: bool,
    watch: bool,
    size: Option<u32>,
    interrupted: &AtomicBool,
) -> Result<(), CurupiraError> {
    run_command_with(
        settings,
        dry_run,
        watch,
        size,
        interrupted,
        &Reporter::Stdio,
    )
    .await
}

/// [`run_command`] with an explicit [`Reporter`] for task progress.
pub async fn run_command_with(
    settings: &ApplicationSettings,
    dry_run: bool,
    watch: bool,
    size: Option<u32>,
    interrupted: &AtomicBool,
    reporter: &Reporter,
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
    let poll_interval = Duration::from_secs(settings.settings.polling.poll_interval_seconds.max(1));
    let workers = settings.settings.max_active_tasks.max(1) as usize;

    let mut running = FuturesUnordered::new();
    let mut dispatched = Dispatched::default();
    let mut admitted = 0_u32;
    let mut failed = 0_u32;

    loop {
        // Fill free workers from a fresh poll; tasks this process already dispatched are skipped.
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
                if !dispatched.first_time(&key) {
                    continue;
                }
                admitted += 1;
                reporter.report(DispatchEvent::Started(TaskStart::describe(settings, &task)));
                running.push(run_task(settings, task, &conn, &vcs, &namespace, reporter));
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
            sleep_unless_interrupted(poll_interval, interrupted).await;
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
        match result {
            Ok(()) => reporter.report(DispatchEvent::Ok(key)),
            Err(err) => {
                failed += 1;
                reporter.report(DispatchEvent::Fail {
                    key,
                    error: err.to_string(),
                });
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
    reporter: &Reporter,
) -> TaskOutcome {
    let key = task.identity.key();
    let result = execute_task(settings, &task, conn, vcs, namespace, reporter).await;
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
    reporter: &Reporter,
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

    let result = run_agent(settings, task, &prepared.cwd, conn, reporter).await;

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

/// The saved session to resume, unless the automation's prompt changed since it was saved: new
/// instructions start a new session instead of continuing under the old ones.
fn resumable(saved: Option<RunningCodingSession>, prompt: &str) -> Option<RunningCodingSession> {
    saved.filter(|session| session.original_prompt == prompt)
}

/// What a resumed session receives. The task's instructions are repeated because the earlier
/// run may have stopped before the agent saw them (for example, when the model was unreachable).
fn resume_message(original_prompt: &str) -> String {
    format!(
        "{RESUME_SESSION_PROMPT} If the session holds no earlier work, start the task below.\n\n\
         Task:\n{original_prompt}"
    )
}

async fn run_agent(
    settings: &ApplicationSettings,
    task: &Task,
    work_dir: &std::path::Path,
    conn: &rusqlite::Connection,
    reporter: &Reporter,
) -> Result<(), CurupiraError> {
    let profile = settings
        .agents
        .profiles
        .get(&task.profile_name)
        .ok_or_else(|| CurupiraError::Dispatch(format!("missing profile {}", task.profile_name)))?;
    let provider = AgentProvider::parse(&profile.provider)?;

    let sessions = RunningSessionRepository::new(conn);
    let existing = resumable(sessions.get(&task.identity.key())?, &task.prompt);
    let (message, session_id, new_session_id) = if let Some(existing) = &existing {
        (
            resume_message(&existing.original_prompt),
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

    let known_session = session_id.clone().or_else(|| new_session_id.clone());
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

    // Only a dashboard follows the output and the session title; `run` skips both.
    let key = task.identity.key();
    let output = reporter.output_sink(&key);
    let session = Arc::new(Mutex::new(known_session));
    let titles = match output {
        Some(_) => {
            agents::build_session_list(provider, profile, work_dir)?.map(|list| TitleWatch {
                list,
                cwd: work_dir,
                env_overrides: &settings.environment.vars,
                provider,
                session: Arc::clone(&session),
            })
        }
        None => None,
    };
    let output = output.map(|forward| -> LineSink {
        let session = Arc::clone(&session);
        Arc::new(move |line: String| {
            if let Ok(mut id) = session.lock() {
                if id.is_none() {
                    *id = agents::session_id_from_line(provider, &line);
                }
            }
            forward(line);
        })
    });

    let timeout = Duration::from_secs(u64::from(settings.settings.task_timeout_minutes) * 60);
    let finished = AtomicBool::new(false);
    let run = async {
        let result = run_process_with_lines(
            &launch.program,
            &launch.args,
            Some(work_dir),
            &launch.env,
            &settings.environment.vars,
            timeout,
            settings.settings.max_output_bytes as usize,
            output,
        )
        .await;
        finished.store(true, Ordering::SeqCst);
        result
    };
    let watch = async {
        if let Some(titles) = &titles {
            titles.run(&finished, &key, reporter).await;
        }
    };
    let (result, ()) = tokio::join!(run, watch);
    let result = result.map_err(CurupiraError::Dispatch)?;

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
            failure_detail(&result.stdout, &result.stderr)
        )));
    }
    Ok(())
}

/// Follows the title a coding agent gives its session, through the provider's session list.
struct TitleWatch<'a> {
    list: agents::HeadlessLaunch,
    cwd: &'a std::path::Path,
    env_overrides: &'a BTreeMap<String, String>,
    provider: AgentProvider,
    /// Known up front for resumed and caller-assigned sessions, else read from the agent's output.
    session: Arc<Mutex<Option<String>>>,
}

impl TitleWatch<'_> {
    const FIRST_LOOK: Duration = Duration::from_secs(3);
    const INTERVAL: Duration = Duration::from_secs(10);

    /// Report the title whenever it changes while the agent runs, and once more after it exits.
    async fn run(&self, finished: &AtomicBool, key: &str, reporter: &Reporter) {
        let mut last: Option<String> = None;
        let mut next = tokio::time::Instant::now() + Self::FIRST_LOOK;
        loop {
            let done = finished.load(Ordering::SeqCst);
            if done || tokio::time::Instant::now() >= next {
                if let Some(title) = self.read().await {
                    if last.as_deref() != Some(title.as_str()) {
                        reporter.report(DispatchEvent::Titled {
                            key: key.to_owned(),
                            title: title.clone(),
                        });
                        last = Some(title);
                    }
                }
                if done {
                    return;
                }
                next = tokio::time::Instant::now() + Self::INTERVAL;
            }
            tokio::time::sleep(Duration::from_millis(200)).await;
        }
    }

    async fn read(&self) -> Option<String> {
        let id = self.session.lock().ok()?.clone()?;
        let listed = run_process(
            &self.list.program,
            &self.list.args,
            Some(self.cwd),
            &self.list.env,
            self.env_overrides,
            Duration::from_secs(30),
            1_000_000,
        )
        .await
        .ok()?;
        if listed.exit_code != 0 {
            return None;
        }
        agents::session_title(self.provider, &String::from_utf8_lossy(&listed.stdout), &id)
    }
}

/// Why an agent failed: its stderr, or else the error it reported on stdout. Agents in JSON
/// mode (OpenCode 2.x) print errors as events on stdout and leave stderr empty.
fn failure_detail(stdout: &[u8], stderr: &[u8]) -> String {
    const MAX: usize = 600;
    let stderr = String::from_utf8_lossy(stderr);
    let stderr = stderr.trim();
    let detail = if stderr.is_empty() {
        let stdout = String::from_utf8_lossy(stdout);
        let mut lines = stdout
            .lines()
            .map(str::trim)
            .filter(|l| !l.is_empty())
            .rev();
        let last = lines.clone().next().unwrap_or_default().to_owned();
        lines
            .find_map(|line| {
                let value: serde_json::Value = serde_json::from_str(line).ok()?;
                let error = value.get("error")?;
                error
                    .get("message")
                    .and_then(serde_json::Value::as_str)
                    .or_else(|| error.as_str())
                    .map(str::to_owned)
            })
            .unwrap_or(last)
    } else {
        stderr.to_owned()
    };
    if detail.chars().count() > MAX {
        let tail: String = detail
            .chars()
            .rev()
            .take(MAX)
            .collect::<Vec<_>>()
            .into_iter()
            .rev()
            .collect();
        format!("…{tail}")
    } else {
        detail
    }
}

#[cfg(test)]
mod tests {
    use std::collections::BTreeMap;

    use super::*;
    use crate::config::{
        AgentDefaults, AgentProfile, AgentsSettings, ApplicationSettings, ExecutionSettings,
        RepositoryConfiguration, ResolvedAutomation,
    };

    #[test]
    fn failure_detail_prefers_stderr_then_the_json_error_on_stdout() {
        assert_eq!(failure_detail(b"ignored", b"  boom\n"), "boom");
        let stdout = br#"{"type":"step"}
{"type":"error","error":{"type":"provider.no-route","message":"Model unavailable: openai/x"}}
"#;
        assert_eq!(failure_detail(stdout, b""), "Model unavailable: openai/x");
        assert_eq!(failure_detail(b"plain\nlast line\n", b""), "last line");
        assert_eq!(failure_detail(b"", b""), "");
        let long = "x".repeat(700);
        assert_eq!(failure_detail(long.as_bytes(), b"").chars().count(), 601);
    }

    #[test]
    fn callback_reporter_receives_events() {
        let seen = Arc::new(std::sync::Mutex::new(Vec::new()));
        let sink = Arc::clone(&seen);
        let reporter = Reporter::Callback(Arc::new(move |event| sink.lock().unwrap().push(event)));
        reporter.report(DispatchEvent::Ok("k".into()));
        reporter.output_sink("k").unwrap()("line".into());
        assert_eq!(
            *seen.lock().unwrap(),
            vec![
                DispatchEvent::Ok("k".into()),
                DispatchEvent::Output {
                    key: "k".into(),
                    line: "line".into()
                }
            ]
        );
        assert!(Reporter::Stdio.output_sink("k").is_none());
    }

    #[tokio::test(start_paused = true)]
    async fn idle_sleep_wakes_when_interrupted() {
        let interrupted = AtomicBool::new(true);
        let started = tokio::time::Instant::now();
        sleep_unless_interrupted(Duration::from_secs(30), &interrupted).await;
        assert!(started.elapsed() < Duration::from_secs(1));
    }

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

    #[cfg(unix)]
    #[tokio::test]
    async fn title_watch_reports_the_agent_session_title_once() {
        use std::os::unix::fs::PermissionsExt;

        let dir = tempfile::tempdir().unwrap();
        let script = dir.path().join("list-sessions");
        std::fs::write(
            &script,
            "#!/bin/sh\nprintf '%s' '[{\"id\":\"ses_1\",\"title\":\"Revisão do PR #223\"},{\"id\":\"ses_2\",\"title\":\"New session - 2026\"}]'\n",
        )
        .unwrap();
        std::fs::set_permissions(&script, std::fs::Permissions::from_mode(0o755)).unwrap();

        let seen = Arc::new(Mutex::new(Vec::new()));
        let sink = Arc::clone(&seen);
        let reporter = Reporter::Callback(Arc::new(move |event| sink.lock().unwrap().push(event)));
        let env = BTreeMap::new();
        let watch = |id: &str| TitleWatch {
            list: agents::HeadlessLaunch {
                program: script.to_string_lossy().into_owned(),
                args: Vec::new(),
                env: Vec::new(),
            },
            cwd: dir.path(),
            env_overrides: &env,
            provider: AgentProvider::OpenCode,
            session: Arc::new(Mutex::new(Some(id.to_owned()))),
        };

        // Finished agents get one last look, which is all that runs here.
        let finished = AtomicBool::new(true);
        watch("ses_1").run(&finished, "k", &reporter).await;
        watch("ses_2").run(&finished, "k2", &reporter).await;
        assert_eq!(
            *seen.lock().unwrap(),
            vec![DispatchEvent::Titled {
                key: "k".into(),
                title: "Revisão do PR #223".into()
            }],
            "placeholder titles are not reported"
        );
    }

    #[test]
    fn a_task_runs_once_per_process_and_again_in_a_new_one() {
        let mut run = Dispatched::default();
        assert!(run.first_time("issue-1"));
        assert!(!run.first_time("issue-1"), "no duplicate in the same run");
        assert!(run.first_time("issue-2"));

        let mut next_run = Dispatched::default();
        assert!(
            next_run.first_time("issue-1"),
            "nothing is remembered across runs"
        );
    }

    #[test]
    fn the_state_database_keeps_no_task_history() {
        let dir = tempfile::tempdir().unwrap();
        let conn = open_db(&dir.path().join("state.sqlite3")).unwrap();
        let mut tables: Vec<String> = conn
            .prepare("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
            .unwrap()
            .query_map([], |row| row.get(0))
            .unwrap()
            .map(Result::unwrap)
            .collect();
        tables.sort();
        assert_eq!(tables, vec!["cron_schedules", "running_sessions"]);
    }

    #[test]
    fn resumed_sessions_get_the_task_again() {
        let message = resume_message("Review PR #223 and merge it.");
        assert!(message.starts_with(RESUME_SESSION_PROMPT));
        assert!(message.ends_with("Task:\nReview PR #223 and merge it."));
    }

    #[test]
    fn a_changed_prompt_starts_a_new_session() {
        let saved = |prompt: &str| {
            Some(RunningCodingSession {
                session_id: "ses_1".into(),
                provider: "opencode".into(),
                original_prompt: prompt.into(),
            })
        };
        assert_eq!(
            resumable(saved("old"), "old").map(|s| s.session_id),
            Some("ses_1".to_string())
        );
        assert!(resumable(saved("old"), "new").is_none());
        assert!(resumable(None, "new").is_none());
    }

    #[test]
    fn task_start_names_pull_requests_and_the_agent_model() {
        let mut settings = settings();
        let mut extra = serde_json::Map::new();
        extra.insert("model".into(), serde_json::json!("openai/gpt-5.5"));
        settings.agents.profiles.insert(
            "p".into(),
            AgentProfile {
                provider: "opencode".into(),
                extra,
            },
        );
        let task = task_from_values(
            &settings,
            &automation("Review ${pull_request_number}"),
            vec![
                pair("pull_request_number", "223"),
                pair("pull_request_title", "bump paths-filter"),
                pair("pull_request_url", "https://github.com/o/r/pull/223"),
            ],
        )
        .unwrap();
        let start = TaskStart::describe(&settings, &task);
        assert_eq!(start.key, task.identity.key());
        assert_eq!(start.title, "#223 bump paths-filter");
        assert_eq!(
            start.url.as_deref(),
            Some("https://github.com/o/r/pull/223")
        );
        assert_eq!(start.agent, "opencode · openai/gpt-5.5");
        assert_eq!(start.prompt, "Review 223");

        let cron = task_from_values(&settings, &automation("Weekly"), vec![]).unwrap();
        let start = TaskStart::describe(&settings, &cron);
        assert_eq!((start.title.as_str(), start.url), ("weekly", None));
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
