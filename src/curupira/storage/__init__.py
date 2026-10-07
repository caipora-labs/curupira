"""Local persistence repositories."""

from curupira.storage.cron import CronScheduleRepository
from curupira.storage.sessions import RunningSessionRepository

__all__ = ["CronScheduleRepository", "RunningSessionRepository"]
