"""Automation configuration Field descriptions for CLI documentation."""

from __future__ import annotations

import pytest

from curupira.tasks.registry import registered


@pytest.mark.parametrize("trigger_type", sorted(registered()))
def test_registered_configuration_models_describe_every_field(trigger_type: str) -> None:
    """Every trigger configuration model exposes non-empty Field descriptions."""
    model = registered()[trigger_type].configuration_model
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

    for name, property_schema in schema.get("properties", {}).items():
        assert (property_schema.get("description") or "").strip(), (
            f"{model.__name__} schema property {name!r} must have a non-empty description"
        )
