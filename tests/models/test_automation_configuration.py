"""Automation configuration Field descriptions for CLI documentation."""

from __future__ import annotations

import pytest

from curupira.models.configuration import (
    AutomationConfigurationBase,
    GitHubAutomationConfiguration,
)
from curupira.tasks.registry import registered


def _assert_model_fields_described(model: type[AutomationConfigurationBase]) -> None:
    """Require non-empty model and property descriptions without Attributes blocks."""
    schema = model.model_json_schema()

    assert (schema.get("description") or "").strip(), (
        f"{model.__name__} model_json_schema() must include a non-empty description"
    )
    assert "Attributes:" not in (model.__doc__ or ""), (
        f"{model.__name__} class docstring must not keep an Attributes: block"
    )

    for name, field in model.model_fields.items():
        assert (field.description or "").strip(), (
            f"{model.__name__}.{name} must have a non-empty Field(description=...)"
        )

    properties = schema.get("properties", {})
    assert "trigger_type" in properties, (
        f"{model.__name__} schema must expose a trigger_type property"
    )
    for name, property_schema in properties.items():
        assert (property_schema.get("description") or "").strip(), (
            f"{model.__name__} schema property {name!r} must have a non-empty description"
        )


@pytest.mark.parametrize(
    "model",
    [AutomationConfigurationBase, GitHubAutomationConfiguration],
)
def test_automation_base_configuration_models_describe_every_field(
    model: type[AutomationConfigurationBase],
) -> None:
    """Shared automation bases expose Field descriptions for inherited fields."""
    _assert_model_fields_described(model)


@pytest.mark.parametrize("trigger_type", sorted(registered()))
def test_registered_configuration_models_describe_every_field(trigger_type: str) -> None:
    """Every trigger configuration model exposes non-empty Field descriptions."""
    _assert_model_fields_described(registered()[trigger_type].configuration_model)
