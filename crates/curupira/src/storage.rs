//! SQLite persistence for cron schedules, completed tasks, and sessions.

use std::path::Path;

use chrono::{DateTime, Utc};
use rusqlite::{params, Connection, OptionalExtension};

use crate::config::Task;
use crate::error::CurupiraError;

/// Open (and migrate) the shared state database.
pub fn open_db(path: &Path) -> Result<Connection, CurupiraError> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| CurupiraError::Runtime(e.to_string()))?;
    }
    let conn = Connection::open(path).map_err(|e| CurupiraError::Runtime(e.to_string()))?;
    conn.execute_batch(
        r#"
        CREATE TABLE IF NOT EXISTS cron_schedules (
            automation_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            pending_scheduled_for TEXT,
            last_scheduled_for TEXT,
            started_at TEXT
        );
        CREATE TABLE IF NOT EXISTS completed_tasks (
            task_key TEXT PRIMARY KEY,
            completed_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS running_sessions (
            task_key TEXT PRIMARY KEY,
            payload TEXT NOT NULL
        );
        "#,
    )
    .map_err(|e| CurupiraError::Runtime(e.to_string()))?;
    Ok(conn)
}

#[derive(Debug, Clone)]
pub struct CronRunState {
    pub automation_id: String,
    pub created_at: DateTime<Utc>,
    pub pending_scheduled_for: Option<DateTime<Utc>>,
    pub last_scheduled_for: Option<DateTime<Utc>>,
    pub started_at: Option<DateTime<Utc>>,
}

pub struct CronScheduleRepository<'a> {
    conn: &'a Connection,
}

impl<'a> CronScheduleRepository<'a> {
    pub fn new(conn: &'a Connection) -> Self {
        Self { conn }
    }

    pub fn preview_state(
        &self,
        automation_id: &str,
    ) -> Result<Option<CronRunState>, CurupiraError> {
        self.get(automation_id)
    }

    pub fn get_or_create(
        &self,
        automation_id: &str,
        now: DateTime<Utc>,
    ) -> Result<CronRunState, CurupiraError> {
        if let Some(state) = self.get(automation_id)? {
            return Ok(state);
        }
        self.conn
            .execute(
                "INSERT INTO cron_schedules (automation_id, created_at) VALUES (?1, ?2)",
                params![automation_id, now.to_rfc3339()],
            )
            .map_err(|e| CurupiraError::Runtime(e.to_string()))?;
        Ok(CronRunState {
            automation_id: automation_id.into(),
            created_at: now,
            pending_scheduled_for: None,
            last_scheduled_for: None,
            started_at: None,
        })
    }

    pub fn get(&self, automation_id: &str) -> Result<Option<CronRunState>, CurupiraError> {
        self.conn
            .query_row(
                "SELECT automation_id, created_at, pending_scheduled_for, last_scheduled_for, started_at
                 FROM cron_schedules WHERE automation_id = ?1",
                params![automation_id],
                |row| {
                    Ok(CronRunState {
                        automation_id: row.get(0)?,
                        created_at: parse_dt(&row.get::<_, String>(1)?)?,
                        pending_scheduled_for: parse_opt_dt(row.get::<_, Option<String>>(2)?)?,
                        last_scheduled_for: parse_opt_dt(row.get::<_, Option<String>>(3)?)?,
                        started_at: parse_opt_dt(row.get::<_, Option<String>>(4)?)?,
                    })
                },
            )
            .optional()
            .map_err(|e| CurupiraError::Runtime(e.to_string()))
    }

    pub fn set_pending(
        &self,
        automation_id: &str,
        occurrence: DateTime<Utc>,
    ) -> Result<Option<CronRunState>, CurupiraError> {
        let updated = self
            .conn
            .execute(
                "UPDATE cron_schedules SET pending_scheduled_for = ?2
                 WHERE automation_id = ?1 AND pending_scheduled_for IS NULL",
                params![automation_id, occurrence.to_rfc3339()],
            )
            .map_err(|e| CurupiraError::Runtime(e.to_string()))?;
        if updated == 0 {
            return Ok(None);
        }
        self.get(automation_id)
    }

    pub fn mark_started(
        &self,
        automation_id: &str,
        now: DateTime<Utc>,
    ) -> Result<(), CurupiraError> {
        self.conn
            .execute(
                "UPDATE cron_schedules SET started_at = ?2 WHERE automation_id = ?1",
                params![automation_id, now.to_rfc3339()],
            )
            .map_err(|e| CurupiraError::Runtime(e.to_string()))?;
        Ok(())
    }

    pub fn complete_run(&self, task: &Task) -> Result<(), CurupiraError> {
        let occurrence = task
            .scheduled_for
            .ok_or_else(|| CurupiraError::Dispatch("cron task missing scheduled_for".into()))?;
        self.conn
            .execute(
                "UPDATE cron_schedules
                 SET pending_scheduled_for = NULL, started_at = NULL, last_scheduled_for = ?2
                 WHERE automation_id = ?1",
                params![task.automation_id, occurrence.to_rfc3339()],
            )
            .map_err(|e| CurupiraError::Runtime(e.to_string()))?;
        self.conn
            .execute(
                "DELETE FROM running_sessions WHERE task_key = ?1",
                params![task.identity.key()],
            )
            .map_err(|e| CurupiraError::Runtime(e.to_string()))?;
        Ok(())
    }
}

pub struct CompletedTaskRepository<'a> {
    conn: &'a Connection,
}

impl<'a> CompletedTaskRepository<'a> {
    pub fn new(conn: &'a Connection) -> Self {
        Self { conn }
    }

    pub fn contains(&self, key: &str) -> Result<bool, CurupiraError> {
        let count: i64 = self
            .conn
            .query_row(
                "SELECT COUNT(1) FROM completed_tasks WHERE task_key = ?1",
                params![key],
                |row| row.get(0),
            )
            .map_err(|e| CurupiraError::Runtime(e.to_string()))?;
        Ok(count > 0)
    }

    pub fn mark(&self, key: &str, at: DateTime<Utc>) -> Result<(), CurupiraError> {
        self.conn
            .execute(
                "INSERT OR IGNORE INTO completed_tasks (task_key, completed_at) VALUES (?1, ?2)",
                params![key, at.to_rfc3339()],
            )
            .map_err(|e| CurupiraError::Runtime(e.to_string()))?;
        Ok(())
    }
}

fn parse_dt(raw: &str) -> std::result::Result<DateTime<Utc>, rusqlite::Error> {
    DateTime::parse_from_rfc3339(raw)
        .map(|dt| dt.with_timezone(&Utc))
        .map_err(|e| {
            rusqlite::Error::FromSqlConversionFailure(0, rusqlite::types::Type::Text, Box::new(e))
        })
}

fn parse_opt_dt(
    raw: Option<String>,
) -> std::result::Result<Option<DateTime<Utc>>, rusqlite::Error> {
    match raw {
        None => Ok(None),
        Some(s) => Ok(Some(parse_dt(&s)?)),
    }
}
