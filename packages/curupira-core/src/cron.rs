//! Built-in cron trigger (in-process; not an extension).

use chrono::{DateTime, TimeZone, Utc};
use chrono_tz::Tz;
use cron::Schedule;
use std::str::FromStr;

use crate::config::{
    expand_user, ApplicationSettings, AutomationTable, ResolvedAutomation, Task, TaskIdentity,
};
use crate::error::CurupiraError;
use crate::storage::{CronRunState, CronScheduleRepository};

/// Validate a cron automation table without extensions.
pub fn validate_automation_table(auto: &AutomationTable) -> Result<(), CurupiraError> {
    let schedule = auto
        .extra
        .get("schedule")
        .and_then(|v| v.as_str())
        .ok_or_else(|| CurupiraError::Config("cron automation requires schedule".into()))?;
    if schedule.split_whitespace().count() != 5 {
        return Err(CurupiraError::Config(
            "schedule must be a valid five-field cron expression".into(),
        ));
    }
    // cron crate uses 6/7 fields with seconds; prepend seconds=0 for five-field expressions.
    let with_seconds = format!("0 {schedule}");
    Schedule::from_str(&with_seconds).map_err(|e| {
        CurupiraError::Config(format!(
            "schedule must be a valid five-field cron expression: {e}"
        ))
    })?;
    if let Some(tz) = auto.extra.get("timezone").and_then(|v| v.as_str()) {
        let _: Tz = tz
            .parse()
            .map_err(|_| CurupiraError::Config(format!("unknown timezone {tz:?}")))?;
    }
    Ok(())
}

/// Poll one cron automation for a due occurrence.
pub fn poll_cron(
    automation: &ResolvedAutomation,
    repo: &CronScheduleRepository<'_>,
    preview: bool,
    now: DateTime<Utc>,
    workspace_dir: &str,
) -> Result<Vec<Task>, CurupiraError> {
    let schedule = automation
        .configuration
        .get("schedule")
        .and_then(|v| v.as_str())
        .ok_or_else(|| CurupiraError::Dispatch("cron missing schedule".into()))?;
    let tz_name = automation
        .configuration
        .get("timezone")
        .and_then(|v| v.as_str())
        .unwrap_or("UTC");
    let tz: Tz = tz_name
        .parse()
        .map_err(|_| CurupiraError::Dispatch(format!("bad timezone {tz_name}")))?;

    let name = &automation.automation_id;
    let state = if preview {
        repo.preview_state(name)?.unwrap_or_else(|| CronRunState {
            automation_id: name.clone(),
            created_at: now,
            pending_scheduled_for: None,
            last_scheduled_for: None,
            started_at: None,
        })
    } else {
        repo.get_or_create(name, now)?
    };

    let occurrence = if let Some(pending) = state.pending_scheduled_for {
        Some(pending)
    } else {
        latest_due_occurrence(schedule, tz, &automation.configuration, &state, now)?
    };

    let Some(occurrence) = occurrence else {
        return Ok(vec![]);
    };

    if !preview
        && state.pending_scheduled_for.is_none()
        && repo.set_pending(name, occurrence)?.is_none()
    {
        return Ok(vec![]);
    }

    let id = occurrence.timestamp().to_string();
    let identity = TaskIdentity {
        automation_id: name.clone(),
        repo: automation.identity_repo.clone(),
        task_type: "cron".into(),
        id,
    };

    Ok(vec![Task {
        identity: identity.clone(),
        automation_id: name.clone(),
        title: name.clone(),
        url: format!("cron://{name}"),
        item: serde_json::json!({}),
        scheduled_for: Some(occurrence),
        prompt: render_prompt(automation, name, &identity.id)?,
        trigger_type: "cron".into(),
        profile_name: automation.profile_name.clone(),
        provider: automation.profile.provider.clone(),
        repository_remote: automation.repository.remote.clone(),
        repository_alias: automation.repository_alias.clone(),
        repository_path: automation.repository.path.clone(),
        setup_script: automation.repository.setup_script.clone(),
        checkout: automation.checkout.clone(),
        workspace_dir: expand_user(workspace_dir).to_string_lossy().into_owned(),
    }])
}

fn latest_due_occurrence(
    schedule: &str,
    tz: Tz,
    configuration: &serde_json::Value,
    state: &CronRunState,
    now: DateTime<Utc>,
) -> Result<Option<DateTime<Utc>>, CurupiraError> {
    let with_seconds = format!("0 {schedule}");
    let schedule =
        Schedule::from_str(&with_seconds).map_err(|e| CurupiraError::Dispatch(e.to_string()))?;

    let local_now = now.with_timezone(&tz);
    let start = if let Some(start_raw) = configuration.get("start_date").and_then(|v| v.as_str()) {
        parse_boundary(start_raw, tz)?
    } else {
        state.created_at.with_timezone(&tz)
    };

    let ceiling = if let Some(end_raw) = configuration.get("end_date").and_then(|v| v.as_str()) {
        let end = parse_boundary(end_raw, tz)?;
        if local_now < end {
            local_now
        } else {
            end
        }
    } else {
        local_now
    };

    // Find previous tick at or before ceiling, not before start, after last_scheduled.
    let mut latest: Option<DateTime<Tz>> = None;
    for dt in schedule
        .after(&(start - chrono::Duration::seconds(1)))
        .take(10_000)
    {
        if dt > ceiling {
            break;
        }
        if dt >= start {
            latest = Some(dt);
        }
    }
    let Some(latest) = latest else {
        return Ok(None);
    };
    let latest_utc = latest.with_timezone(&Utc);
    if let Some(last) = state.last_scheduled_for {
        if latest_utc <= last {
            return Ok(None);
        }
    }
    Ok(Some(latest_utc))
}

fn parse_boundary(raw: &str, tz: Tz) -> Result<DateTime<Tz>, CurupiraError> {
    if let Ok(dt) = DateTime::parse_from_rfc3339(raw) {
        return Ok(dt.with_timezone(&tz));
    }
    // date-only YYYY-MM-DD
    if let Ok(naive) = chrono::NaiveDate::parse_from_str(raw, "%Y-%m-%d") {
        let naive_dt = naive
            .and_hms_opt(0, 0, 0)
            .ok_or_else(|| CurupiraError::Config(format!("bad date {raw}")))?;
        return tz
            .from_local_datetime(&naive_dt)
            .single()
            .ok_or_else(|| CurupiraError::Config(format!("ambiguous date {raw}")));
    }
    Err(CurupiraError::Config(format!("invalid date {raw:?}")))
}

fn render_prompt(
    automation: &ResolvedAutomation,
    name: &str,
    occurrence: &str,
) -> Result<String, CurupiraError> {
    let vars = crate::prompt::task_vars(
        &[
            ("repo", automation.identity_repo.clone()),
            ("repository", automation.repository_alias.clone()),
            ("automation", name.to_string()),
            ("automation_id", name.to_string()),
            ("task_type", "cron".to_string()),
            ("task_number", occurrence.to_string()),
            ("task_title", name.to_string()),
            ("task_body", String::new()),
            ("task_url", format!("cron://{name}")),
        ],
        &serde_json::json!({}),
    );
    crate::prompt::render(name, &automation.prompt, &vars)
}

/// Mark cron lifecycle after agent start.
pub fn on_task_started(
    repo: &CronScheduleRepository<'_>,
    task: &Task,
) -> Result<(), CurupiraError> {
    repo.mark_started(&task.automation_id, Utc::now())
}

/// Complete cron run after agent finish.
pub fn on_task_finished(
    repo: &CronScheduleRepository<'_>,
    task: &Task,
) -> Result<(), CurupiraError> {
    repo.complete_run(task)
}

/// Helper for settings-level cron presence checks in tests.
#[allow(dead_code)]
pub fn has_cron(settings: &ApplicationSettings) -> bool {
    settings
        .automations
        .values()
        .any(|a| a.effective_trigger_type() == "cron")
}
