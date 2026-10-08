"""Pure formatting helpers for the orchestrator dashboard."""

from __future__ import annotations

from datetime import UTC, datetime

from curupira.agents.registry import registered
from curupira.models import Task

_ACTIVITY_ALERT_RATIO = 0.8


def provider_label(provider: str) -> str:
    """Map a coding-agent provider id to its display name."""
    adapter = registered().get(provider)
    return adapter.display_name if adapter is not None else provider


def format_elapsed(started_at: datetime, *, now: datetime | None = None) -> str:
    """Format elapsed wall time as ``HH:MM:SS``."""
    current = now if now is not None else datetime.now(UTC)
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    elapsed = max(0, int((current - started_at).total_seconds()))
    hours, rem = divmod(elapsed, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_memory(used_bytes: int, total_bytes: int) -> str:
    """Render used/total memory in gibibytes."""
    used_gb = used_bytes / (1024**3)
    total_gb = total_bytes / (1024**3)
    return f"{used_gb:.1f} GB / {total_gb:.1f} GB"


def activity_near_limit(active: int, limit: int) -> bool:
    """Return True when active tasks are at or above 80% of the configured limit."""
    if limit <= 0:
        return False
    return active / limit >= _ACTIVITY_ALERT_RATIO


def task_display_id(task: Task) -> str:
    """Return a compact numeric-looking id for the agents table."""
    raw = task.identity.id
    if raw.isdigit():
        return f"#{raw}"
    return f"#{abs(hash(task.identity.key)) % 1000:03d}"


def task_description(task: Task) -> str:
    """Prefer the task title, falling back to repo/id or cron markers."""
    title = task.title.strip()
    if title:
        return title
    identity = task.identity
    if identity.task_type == "cron":
        return f"{identity.automation_id} cron"
    return f"{identity.repo}#{identity.id}"
