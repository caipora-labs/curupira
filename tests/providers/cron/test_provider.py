"""Cron trigger registration, prompt behavior, and feed construction."""

from datetime import UTC, datetime
from pathlib import Path

from curupira.models import PollingSettings, Task, TaskIdentity
from curupira.models.items import CronItem
from curupira.providers.cron import CronTaskFeed, CronTrigger
from curupira.storage import CronScheduleRepository
from curupira.tasks.base import FeedDependencies
from curupira.tasks.registry import get
from tests.helpers import resolved_automation


def test_cron_trigger_is_registered_without_extra_prompt_fields(tmp_path: Path) -> None:
    trigger = get("cron")
    automation = resolved_automation(tmp_path, "maintenance", "cron")
    scheduled_for = datetime(2026, 10, 1, 9, tzinfo=UTC)
    task = Task(
        identity=TaskIdentity(
            automation_id="maintenance",
            repo="api",
            task_type="cron",
            id=str(int(scheduled_for.timestamp())),
        ),
        automation=automation,
        title="maintenance",
        url="cron://maintenance",
        item=CronItem(),
        scheduled_for=scheduled_for,
    )

    assert isinstance(trigger, CronTrigger)
    assert trigger.item_model is CronItem
    assert trigger.prompt_fields() == frozenset()
    assert trigger.prompt_context(task) == {}

    repository = CronScheduleRepository(tmp_path / "state.sqlite3")
    feed = trigger.build_feed(
        automation,
        FeedDependencies(
            polling=PollingSettings(),
            cron=repository,
            state_db_path=tmp_path / "state.sqlite3",
        ),
    )
    assert isinstance(feed, CronTaskFeed)
    assert feed.automation is automation
