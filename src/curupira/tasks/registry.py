"""Registry for built-in and plugin trigger implementations."""

from curupira.tasks.base import Trigger

_TRIGGERS: dict[str, Trigger] = {}
_ALIASES: dict[str, Trigger] = {}


def register(trigger: Trigger) -> None:
    """Register one trigger implementation for its declared type."""
    trigger_type = trigger.trigger_type
    if trigger_type in _TRIGGERS or trigger_type in _ALIASES:
        raise ValueError(f"trigger type already registered: {trigger_type}")
    _validate_configuration_model(trigger)
    _validate_item_model(trigger)
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
    _ensure_loaded()
    try:
        return _TRIGGERS.get(trigger_type) or _ALIASES[trigger_type]
    except KeyError as error:
        raise ValueError(f"unknown trigger type: {trigger_type}") from error


def registered() -> dict[str, Trigger]:
    """Return every canonical trigger type, built-in triggers first."""
    _ensure_loaded()
    return dict(_TRIGGERS)


def _ensure_loaded() -> None:
    # Built-ins register on import and must precede plugins so collisions are rejected.
    import curupira.tasks  # noqa: F401
    from curupira.plugins import load_plugins

    load_plugins()


def _validate_configuration_model(trigger: Trigger) -> None:
    from curupira.models.configuration import AutomationConfigurationBase

    model = getattr(trigger, "configuration_model", None)
    if not isinstance(model, type) or not issubclass(model, AutomationConfigurationBase):
        raise ValueError(
            f"trigger {trigger.trigger_type!r} must declare a configuration_model "
            "that extends AutomationConfigurationBase"
        )
    default = model.model_fields["trigger_type"].default
    if default != trigger.trigger_type:
        raise ValueError(
            f"configuration_model for {trigger.trigger_type!r} must default "
            f"trigger_type to {trigger.trigger_type!r}, not {default!r}"
        )


def _validate_item_model(trigger: Trigger) -> None:
    from curupira.models.base import ValidatedModel

    model = getattr(trigger, "item_model", None)
    if not isinstance(model, type) or not issubclass(model, ValidatedModel):
        raise ValueError(
            f"trigger {trigger.trigger_type!r} must declare an item_model "
            "that extends ValidatedModel"
        )
