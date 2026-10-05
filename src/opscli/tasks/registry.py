"""Registry for trigger implementations."""

from opscli.tasks.base import Trigger

_TRIGGERS: dict[str, Trigger] = {}


def register(trigger: Trigger) -> None:
    """Register one trigger implementation for its declared type."""
    trigger_type = trigger.trigger_type
    if trigger_type in _TRIGGERS:
        raise ValueError(f"trigger type already registered: {trigger_type}")
    _TRIGGERS[trigger_type] = trigger


def get(trigger_type: str) -> Trigger:
    """Return the trigger for a type, or raise an actionable error."""
    try:
        return _TRIGGERS[trigger_type]
    except KeyError as error:
        raise ValueError(f"unknown trigger type: {trigger_type}") from error
