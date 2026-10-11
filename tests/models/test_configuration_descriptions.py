"""Field descriptions for execution, polling, and repository configuration models."""

import pytest

from curupira.models.configuration import (
    ExecutionSettings,
    PollingSettings,
    RepositoryConfiguration,
)


@pytest.mark.parametrize(
    "model",
    [PollingSettings, ExecutionSettings, RepositoryConfiguration],
)
def test_settings_models_expose_non_empty_field_descriptions(
    model: type[PollingSettings] | type[ExecutionSettings] | type[RepositoryConfiguration],
) -> None:
    """JSON Schema and model metadata carry descriptions without Attributes doc blocks."""
    docstring = model.__doc__ or ""
    assert docstring.strip()
    assert "Attributes:" not in docstring

    schema = model.model_json_schema()
    assert schema.get("description", "").strip()

    properties = schema["properties"]
    assert properties
    for name, field_info in model.model_fields.items():
        assert field_info.description is not None, name
        assert field_info.description.strip(), name
        property_schema = properties[name]
        description = property_schema.get("description", "")
        if not description and "allOf" in property_schema:
            description = next(
                (
                    part["description"]
                    for part in property_schema["allOf"]
                    if isinstance(part, dict) and part.get("description")
                ),
                "",
            )
        assert description.strip(), name
