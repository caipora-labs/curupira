"""Coding-agent profile models expose field descriptions for CLI docs."""

import inspect

import pytest

from curupira.agents.registry import registered
from curupira.models.profiles import CliProfileBase


def _profile_models() -> list[tuple[str, type[CliProfileBase]]]:
    models: list[tuple[str, type[CliProfileBase]]] = [("CliProfileBase", CliProfileBase)]
    for provider, adapter in sorted(registered().items()):
        models.append((provider, adapter.profile_model))
    return models


@pytest.mark.parametrize(("name", "model"), _profile_models())
def test_profile_model_fields_have_descriptions(
    name: str,
    model: type[CliProfileBase],
) -> None:
    schema = model.model_json_schema()
    assert isinstance(schema.get("description"), str)
    assert schema["description"].strip()
    assert "Attributes:" not in (inspect.getdoc(model) or "")
    assert "Attributes:" not in (model.__doc__ or "")

    properties = schema.get("properties")
    assert isinstance(properties, dict)
    assert properties
    for field_name, field_schema in properties.items():
        description = field_schema.get("description")
        assert isinstance(description, str), f"{name}.{field_name} missing description"
        assert description.strip(), f"{name}.{field_name} has an empty description"
