"""Cron trigger registration, prompt behavior, and feed construction."""

from pathlib import Path
from typing import cast

from curupi.clients.gh import GhClient
from curupi.models import PollingSettings
from curupi.storage import CronScheduleRepository
from curupi.tasks.base import FeedDependencies
from curupi.tasks.cron import CronTaskFeed, CronTrigger
from curupi.tasks.registry import get
from tests.helpers import issue_task, resolved_automation


def test_cron_trigger_is_registered_without_extra_prompt_fields(tmp_path: Path) -> None:
    trigger = get("cron")
    task = issue_task(tmp_path)

    assert isinstance(trigger, CronTrigger)
    assert trigger.prompt_fields() == frozenset()
    assert trigger.prompt_context(task) == {}

    automation = resolved_automation(tmp_path, "maintenance", "cron")
    repository = CronScheduleRepository(tmp_path / "state.sqlite3")
    feed = trigger.build_feed(
        automation,
        FeedDependencies(
            polling=PollingSettings(),
            gh=cast(GhClient, None),
            cron=repository,
        ),
    )
    assert isinstance(feed, CronTaskFeed)
    assert feed.automation is automation
