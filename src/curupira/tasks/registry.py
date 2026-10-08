"""Registry for trigger implementations bound to specific configuration types."""

from curupira.tasks.base import Trigger

_TRIGGERS: dict[str, Trigger] = {}
_ALIASES: dict[str, Trigger] = {}
_BY_CONFIGURATION: dict[type, Trigger] = {}


def register(trigger: Trigger) -> None:
    """Register one trigger for its task type and configuration class."""
    trigger_type = trigger.trigger_type
    configuration_type = trigger.configuration_type
    if trigger_type in _TRIGGERS or trigger_type in _ALIASES:
        raise ValueError(f"trigger type already registered: {trigger_type}")
    if configuration_type in _BY_CONFIGURATION:
        raise ValueError(f"configuration type already registered: {configuration_type.__name__}")
    _TRIGGERS[trigger_type] = trigger
    _BY_CONFIGURATION[configuration_type] = trigger


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
    """Return the trigger for a task type, or raise an actionable error."""
    try:
        return _TRIGGERS.get(trigger_type) or _ALIASES[trigger_type]
    except KeyError as error:
        raise ValueError(f"unknown trigger type: {trigger_type}") from error


def for_configuration(configuration: object) -> Trigger:
    """Return the trigger bound to a concrete automation configuration class."""
    try:
        return _BY_CONFIGURATION[type(configuration)]
    except KeyError as error:
        raise ValueError(
            f"no trigger registered for configuration type: {type(configuration).__name__}"
        ) from error
