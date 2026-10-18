"""Convert one trigger return value into protocol key/value pairs, or null."""

from __future__ import annotations

import collections.abc
import dataclasses
import json
import math
import types
import typing
from typing import Any, get_origin

from .errors import SerializationError, ValidationError
from .types import is_collection_type, unwrap_optional

Pair = dict[str, str]


def serialize_trigger_result(
    value: Any, return_annotation: Any, *, trigger_name: str
) -> list[Pair] | None:
    """Return protocol pairs, or None when the trigger found nothing.

    ``None`` is the only input that becomes protocol null. A field whose value
    is ``None`` becomes the string ``null`` inside a list of pairs.
    """
    if value is None:
        return None

    if _is_multi_value(value):
        raise SerializationError(
            f"trigger {trigger_name!r}: must return one object or None, not a collection"
        )

    if is_collection_type(return_annotation):
        raise SerializationError(
            f"trigger {trigger_name!r}: return annotation must not be a collection"
        )

    if return_annotation is not typing.Any and return_annotation is not None:
        _validate_against_annotation(value, return_annotation, trigger_name=trigger_name)

    return to_key_values(value, trigger_name=trigger_name)


def to_key_values(value: Any, *, trigger_name: str) -> list[Pair]:
    """Convert one mapping, dataclass, or Pydantic model into string pairs."""
    mapping = _as_mapping(value, trigger_name=trigger_name)
    seen: set[str] = set()
    pairs: list[Pair] = []
    for key, item in mapping.items():
        if not isinstance(key, str):
            raise SerializationError(f"trigger {trigger_name!r}: key {key!r} is not a string")
        if key == "" or "}" in key or "${" in key:
            raise SerializationError(
                f"trigger {trigger_name!r}: key {key!r} cannot be used as a template placeholder"
            )
        if key in seen:
            raise SerializationError(f"trigger {trigger_name!r}: duplicate key {key!r}")
        seen.add(key)
        pairs.append({"key": key, "value": stringify_value(item, trigger_name=trigger_name)})
    return pairs


def stringify_value(value: Any, *, trigger_name: str) -> str:
    """Render one field value as a string. Nested objects become compact JSON."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        _reject_non_finite(value, trigger_name=trigger_name)
        return json.dumps(value)
    if value is None:
        return "null"
    compatible = to_json_compatible(value, trigger_name=trigger_name)
    try:
        return json.dumps(
            compatible,
            separators=(",", ":"),
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise SerializationError(
            f"trigger {trigger_name!r}: value of type {type(value).__name__} is not serializable"
        ) from exc


def to_json_compatible(value: Any, *, trigger_name: str) -> Any:
    """Convert a nested value to a JSON-compatible structure without coercing keys."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        _reject_non_finite(value, trigger_name=trigger_name)
        return value
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [to_json_compatible(item, trigger_name=trigger_name) for item in value]
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: to_json_compatible(getattr(value, field.name), trigger_name=trigger_name)
            for field in dataclasses.fields(value)
        }
    if _is_pydantic_instance(value):
        dumped = value.model_dump(mode="json")
        return to_json_compatible(dumped, trigger_name=trigger_name)
    if isinstance(value, collections.abc.Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise SerializationError(
                    f"trigger {trigger_name!r}: nested key {key!r} is not a string"
                )
            if key in out:
                raise SerializationError(f"trigger {trigger_name!r}: duplicate nested key {key!r}")
            out[key] = to_json_compatible(item, trigger_name=trigger_name)
        return out
    raise SerializationError(
        f"trigger {trigger_name!r}: value of type {type(value).__name__} is not serializable"
    )


def _as_mapping(value: Any, *, trigger_name: str) -> collections.abc.Mapping[Any, Any]:
    if isinstance(value, (str, bool, int, float)):
        raise SerializationError(
            f"trigger {trigger_name!r}: return value must be a mapping, dataclass, or model, "
            f"not {type(value).__name__}"
        )
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {field.name: getattr(value, field.name) for field in dataclasses.fields(value)}
    if _is_pydantic_instance(value):
        dumped = value.model_dump(mode="json")
        if not isinstance(dumped, collections.abc.Mapping):
            raise SerializationError(
                f"trigger {trigger_name!r}: model did not serialize to an object"
            )
        return dumped
    if isinstance(value, collections.abc.Mapping):
        return value
    raise SerializationError(
        f"trigger {trigger_name!r}: return value of type {type(value).__name__} "
        "is not a mapping, dataclass, or model"
    )


def _reject_non_finite(value: float, *, trigger_name: str) -> None:
    if math.isnan(value) or math.isinf(value):
        raise SerializationError(
            f"trigger {trigger_name!r}: non-finite number {value!r} is not serializable"
        )


def _is_multi_value(value: Any) -> bool:
    if isinstance(value, (list, tuple, set, frozenset)):
        return True
    if isinstance(value, types.GeneratorType):
        return True
    return isinstance(value, collections.abc.Iterator) and not isinstance(
        value, (str, bytes, dict, collections.abc.Mapping)
    )


def _validate_against_annotation(value: Any, annotation: Any, *, trigger_name: str) -> None:
    from .types import coerce_value

    inner, _allows_none = unwrap_optional(annotation)
    origin = get_origin(inner)

    if origin in {list, tuple, set, frozenset}:
        raise SerializationError(
            f"trigger {trigger_name!r}: return annotation must not be a collection"
        )

    if inner in {str, int, float, bool}:
        raise SerializationError(
            f"trigger {trigger_name!r}: return annotation must be a mapping, dataclass, or model, "
            f"not {annotation!r}"
        )

    if origin is dict or inner is dict or _is_typed_dict(inner):
        if isinstance(value, collections.abc.Mapping):
            return
        raise SerializationError(
            f"trigger {trigger_name!r}: return value does not match annotation {annotation!r}"
        )

    if isinstance(inner, type) and isinstance(value, inner):
        return

    try:
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            candidate: Any = {
                field.name: getattr(value, field.name) for field in dataclasses.fields(value)
            }
        elif _is_pydantic_instance(value):
            candidate = value.model_dump(mode="json")
        else:
            candidate = value
        coerce_value(annotation, candidate, context=f"trigger {trigger_name!r} return")
    except (ValidationError, SerializationError) as exc:
        raise SerializationError(
            f"trigger {trigger_name!r}: return value incompatible with annotation: {exc}"
        ) from exc


def _is_typed_dict(annotation: Any) -> bool:
    return isinstance(annotation, type) and typing.is_typeddict(annotation)


def _is_pydantic_instance(value: Any) -> bool:
    try:
        from pydantic import BaseModel
    except ImportError:
        return False
    return isinstance(value, BaseModel)
