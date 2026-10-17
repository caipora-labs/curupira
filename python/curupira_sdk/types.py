"""Type introspection helpers for JSON Schema and value conversion."""

from __future__ import annotations

import dataclasses
import types
import typing
from typing import Any, get_args, get_origin

from .errors import RegistrationError, SerializationError, ValidationError

_SCALAR_SCHEMA: dict[type, dict[str, Any]] = {
    str: {"type": "string"},
    int: {"type": "integer"},
    float: {"type": "number"},
    bool: {"type": "boolean"},
}


def _is_typed_dict(annotation: Any) -> bool:
    return isinstance(annotation, type) and typing.is_typeddict(annotation)


def _is_pydantic_model(annotation: Any) -> bool:
    try:
        from pydantic import BaseModel
    except ImportError:
        return False
    return isinstance(annotation, type) and issubclass(annotation, BaseModel)


def _require_pydantic(context: str) -> Any:
    try:
        from pydantic import BaseModel
    except ImportError as exc:
        raise RegistrationError(
            f"{context}: Pydantic models require the optional dependency "
            "`curupira-sdk[pydantic]` (pydantic>=2,<3)"
        ) from exc
    return BaseModel


def unwrap_optional(annotation: Any) -> tuple[Any, bool]:
    """Return (inner_type, allows_none)."""
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is typing.Union or origin is types.UnionType:
        non_none = [a for a in args if a is not type(None)]
        allows_none = len(non_none) != len(args)
        if len(non_none) == 1:
            return non_none[0], allows_none
        if allows_none:
            combined = non_none[0]
            for option in non_none[1:]:
                combined |= option
            return combined, True
        return annotation, False
    return annotation, False


def type_to_json_schema(annotation: Any, *, context: str) -> dict[str, Any]:
    """Convert a type annotation to a JSON Schema fragment."""
    if annotation is typing.Any or annotation is None:
        raise RegistrationError(f"{context}: untyped parameters are not supported")

    inner, allows_none = unwrap_optional(annotation)
    schema = _concrete_schema(inner, context=context)
    if allows_none:
        return {"anyOf": [schema, {"type": "null"}]}
    return schema


def _concrete_schema(annotation: Any, *, context: str) -> dict[str, Any]:
    origin = get_origin(annotation)
    args = get_args(annotation)

    if annotation is type(None):
        return {"type": "null"}

    if isinstance(annotation, type) and annotation in _SCALAR_SCHEMA:
        return dict(_SCALAR_SCHEMA[annotation])

    if origin is list or annotation is list:
        if not args:
            raise RegistrationError(f"{context}: list requires an item type annotation")
        return {"type": "array", "items": type_to_json_schema(args[0], context=f"{context}[]")}

    if origin is dict or annotation is dict:
        if len(args) != 2 or args[0] is not str:
            raise RegistrationError(f"{context}: only dict[str, T] is supported")
        return {
            "type": "object",
            "additionalProperties": type_to_json_schema(args[1], context=f"{context}.value"),
        }

    if origin is typing.Union or origin is types.UnionType:
        return {"anyOf": [type_to_json_schema(a, context=context) for a in args]}

    if dataclasses.is_dataclass(annotation) and isinstance(annotation, type):
        return _dataclass_schema(annotation, context=context)

    if _is_typed_dict(annotation):
        return _typed_dict_schema(annotation, context=context)

    if _is_pydantic_model(annotation):
        _require_pydantic(context)
        return annotation.model_json_schema()  # type: ignore[no-any-return]

    # Detect pydantic-looking BaseModel subclasses when pydantic is missing.
    if isinstance(annotation, type) and any(
        base.__name__ == "BaseModel" for base in getattr(annotation, "__mro__", ())
    ):
        _require_pydantic(context)

    raise RegistrationError(
        f"{context}: unsupported type {annotation!r}; use scalars, list[T], "
        "dict[str, T], dataclass, TypedDict, or optional Pydantic models"
    )


def _dataclass_field_types(cls: type) -> dict[str, Any]:
    try:
        return typing.get_type_hints(cls)
    except Exception:  # noqa: BLE001
        return {f.name: f.type for f in dataclasses.fields(cls)}


def _dataclass_schema(cls: type, *, context: str) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    hints = _dataclass_field_types(cls)
    for field in dataclasses.fields(cls):
        annotation = hints.get(field.name, field.type)
        properties[field.name] = type_to_json_schema(annotation, context=f"{context}.{field.name}")
        if (
            field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING  # type: ignore[comparison-overlap]
        ):
            required.append(field.name)
        elif field.default is not dataclasses.MISSING:
            try:
                properties[field.name] = {
                    **properties[field.name],
                    "default": _json_safe(field.default),
                }
            except SerializationError:
                pass
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    schema["additionalProperties"] = False
    return schema


def _typed_dict_schema(cls: type, *, context: str) -> dict[str, Any]:
    hints = typing.get_type_hints(cls)
    required_keys = set(getattr(cls, "__required_keys__", hints.keys()))
    properties = {
        name: type_to_json_schema(hint, context=f"{context}.{name}") for name, hint in hints.items()
    }
    schema: dict[str, Any] = {"type": "object", "properties": properties}
    required = [name for name in hints if name in required_keys]
    if required:
        schema["required"] = required
    schema["additionalProperties"] = False
    return schema


def coerce_value(annotation: Any, value: Any, *, context: str) -> Any:
    """Validate and coerce a JSON value against an annotation."""
    inner, allows_none = unwrap_optional(annotation)
    if value is None:
        if allows_none:
            return None
        raise ValidationError(f"{context}: expected a value, got null")
    return _coerce_concrete(inner, value, context=context)


def _coerce_concrete(annotation: Any, value: Any, *, context: str) -> Any:
    origin = get_origin(annotation)
    args = get_args(annotation)

    if annotation is str:
        if not isinstance(value, str):
            raise ValidationError(f"{context}: expected string")
        return value
    if annotation is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValidationError(f"{context}: expected integer")
        return value
    if annotation is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError(f"{context}: expected number")
        return float(value)
    if annotation is bool:
        if not isinstance(value, bool):
            raise ValidationError(f"{context}: expected boolean")
        return value

    if origin is list:
        if not isinstance(value, list):
            raise ValidationError(f"{context}: expected array")
        return [
            coerce_value(args[0], item, context=f"{context}[{i}]") for i, item in enumerate(value)
        ]

    if origin is dict:
        if not isinstance(value, dict):
            raise ValidationError(f"{context}: expected object")
        return {
            str(key): coerce_value(args[1], item, context=f"{context}.{key}")
            for key, item in value.items()
        }

    if origin is typing.Union or origin is types.UnionType:
        errors: list[str] = []
        for option in args:
            if option is type(None):
                continue
            try:
                return coerce_value(option, value, context=context)
            except (ValidationError, RegistrationError) as exc:
                errors.append(str(exc))
        raise ValidationError(
            f"{context}: value matched none of the union variants ({'; '.join(errors)})"
        )

    if dataclasses.is_dataclass(annotation) and isinstance(annotation, type):
        if not isinstance(value, dict):
            raise ValidationError(f"{context}: expected object for dataclass")
        kwargs: dict[str, Any] = {}
        fields = {f.name: f for f in dataclasses.fields(annotation)}
        hints = _dataclass_field_types(annotation)
        unknown = set(value) - set(fields)
        if unknown:
            raise ValidationError(f"{context}: unknown fields {sorted(unknown)}")
        for name, field in fields.items():
            field_type = hints.get(name, field.type)
            if name in value:
                kwargs[name] = coerce_value(field_type, value[name], context=f"{context}.{name}")
            elif field.default is not dataclasses.MISSING:
                kwargs[name] = field.default
            elif field.default_factory is not dataclasses.MISSING:  # type: ignore[comparison-overlap]
                kwargs[name] = field.default_factory()  # type: ignore[misc]
            else:
                raise ValidationError(f"{context}: missing required field {name!r}")
        return annotation(**kwargs)

    if _is_typed_dict(annotation):
        if not isinstance(value, dict):
            raise ValidationError(f"{context}: expected object for TypedDict")
        hints = typing.get_type_hints(annotation)
        required_keys = set(getattr(annotation, "__required_keys__", hints.keys()))
        unknown = set(value) - set(hints)
        if unknown:
            raise ValidationError(f"{context}: unknown fields {sorted(unknown)}")
        out: dict[str, Any] = {}
        for name, hint in hints.items():
            if name in value:
                out[name] = coerce_value(hint, value[name], context=f"{context}.{name}")
            elif name in required_keys:
                raise ValidationError(f"{context}: missing required field {name!r}")
        return out

    if _is_pydantic_model(annotation):
        _require_pydantic(context)
        try:
            return annotation.model_validate(value)  # type: ignore[no-any-return]
        except Exception as exc:
            raise ValidationError(f"{context}: {exc}") from exc

    raise ValidationError(f"{context}: unsupported type {annotation!r}")


def dump_value(value: Any) -> Any:
    """Convert a Python value to a JSON-serializable structure."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [dump_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): dump_value(item) for key, item in value.items()}
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: dump_value(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if _is_pydantic_model(type(value)):
        return value.model_dump(mode="json")  # type: ignore[no-any-return]
    raise SerializationError(f"value of type {type(value)!r} is not JSON-serializable")


def _json_safe(value: Any) -> Any:
    return dump_value(value)


def prompt_fields_for_return(annotation: Any) -> list[str]:
    """Derive prompt placeholder field names from a return annotation."""
    if annotation is typing.Any or annotation is None or annotation is type(None):
        return []
    inner, _ = unwrap_optional(annotation)
    if dataclasses.is_dataclass(inner) and isinstance(inner, type):
        return [f.name for f in dataclasses.fields(inner)]
    if _is_typed_dict(inner):
        return list(typing.get_type_hints(inner))
    if _is_pydantic_model(inner):
        return list(inner.model_fields)  # type: ignore[attr-defined]
    if isinstance(inner, type) and inner in _SCALAR_SCHEMA:
        return ["value"]
    origin = get_origin(inner)
    if origin is dict:
        return []
    return []


def is_collection_type(annotation: Any) -> bool:
    """Return True when the annotation denotes a multi-value collection."""
    if annotation is typing.Any or annotation is None:
        return False
    inner, _ = unwrap_optional(annotation)
    origin = get_origin(inner) or inner
    if origin in {list, tuple, set, frozenset}:
        return True
    return origin in {
        typing.Iterable,
        typing.Iterator,
        typing.Generator,
        typing.AsyncGenerator,
    }
