"""Cron trigger registration and prompt behavior."""

from opscli.tasks.cron import CronTrigger
from opscli.tasks.registry import get


def test_cron_trigger_is_registered_without_extra_prompt_fields() -> None:
    trigger = get("cron")

    assert isinstance(trigger, CronTrigger)
    assert trigger.prompt_fields() == frozenset()
