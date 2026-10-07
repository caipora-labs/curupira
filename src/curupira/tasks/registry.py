"""Registry for trigger implementations."""

from curupira.tasks.base import Trigger

_TRIGGERS: dict[str, Trigger] = {}
_ALIASES: dict[str, Trigger] = {}


def register(trigger: Trigger) -> None:
    """Register one trigger implementation for its declared type."""
    trigger_type = trigger.trigger_type
    if trigger_type in _TRIGGERS or trigger_type in _ALIASES:
        raise ValueError(f"trigger type already registered: {trigger_type}")
    _TRIGGERS[trigger_type] = trigger


def register_alias(trigger_type: str, alias: str) -> None:
    """Register an alternate name for an already registered trigger."""
    if alias in _TRIGGERS or alias in _ALIASES:
        raise ValueError(f"trigger alias already registered: {alias}")
    try:
        trigger = _TRIGGERS[trigger_type]
    except KeyError as error:
        raise ValueError(f"unknown trigger type for alias {alias}: {trigger_type}") from error
    _ALIASES[alias] = trigger


def get(trigger_type: str) -> Trigger:
    """Return the trigger for a type, or raise an actionable error."""
    try:
        return _TRIGGERS.get(trigger_type) or _ALIASES[trigger_type]
    except KeyError as error:
        raise ValueError(f"unknown trigger type: {trigger_type}") from error
