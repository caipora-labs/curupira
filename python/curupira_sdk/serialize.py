"""Validate and serialize a single trigger result or None."""

from __future__ import annotations

import collections.abc
import dataclasses
import types
import typing
from typing import Any, get_origin

from .errors import SerializationError, ValidationError
from .types import dump_value, is_collection_type, unwrap_optional


def serialize_trigger_result(
    value: Any, return_annotation: Any, *, trigger_name: str
) -> dict[str, Any] | None:
    """Return a host task envelope, or None when the trigger has no item."""
    if _is_multi_value(value):
        raise SerializationError(
            f"trigger {trigger_name!r}: must return a single item or None, not a collection"
        )

    if value is None:
        return None

    if is_collection_type(return_annotation):
        raise SerializationError(
            f"trigger {trigger_name!r}: return annotation must not be a collection"
        )

    if return_annotation is not typing.Any and return_annotation is not None:
        _validate_against_annotation(value, return_annotation, trigger_name=trigger_name)

    try:
        payload = dump_value(value)
    except SerializationError as exc:
        raise SerializationError(f"trigger {trigger_name!r}: {exc}") from exc

    return envelope_from_payload(payload, trigger_name=trigger_name)


def envelope_from_payload(payload: Any, *, trigger_name: str) -> dict[str, Any]:
    """Build `{id, title, url, item}` for the Rust host."""
    if isinstance(payload, (str, int, float, bool)):
        text = str(payload)
        return {"id": text, "title": text, "url": "", "item": {"value": payload}}

    if not isinstance(payload, dict):
        raise SerializationError(
            f"trigger {trigger_name!r}: return value must serialize to an object or scalar"
        )

    item = dict(payload)
    task_id = item.get("id")
    if task_id is None and "number" in item:
        task_id = item["number"]
    if task_id is None:
        raise SerializationError(
            f"trigger {trigger_name!r}: return object must include an 'id' field "
            "(or 'number' for issue-like items)"
        )
    title = item.get("title") or item.get("name") or str(task_id)
    url = item.get("url") or ""
    return {
        "id": str(task_id),
        "title": str(title),
        "url": str(url),
        "item": item,
    }


def _is_multi_value(value: Any) -> bool:
    if isinstance(value, (list, tuple, set, frozenset)):
        return True
    if isinstance(value, types.GeneratorType):
        return True
    if isinstance(value, collections.abc.Iterator) and not isinstance(
        value, (str, bytes, dict, collections.abc.Mapping)
    ):
        return True
    return False


def _validate_against_annotation(value: Any, annotation: Any, *, trigger_name: str) -> None:
    from .types import coerce_value

    inner, _allows_none = unwrap_optional(annotation)
    origin = get_origin(inner)

    if origin is list or origin is tuple or origin is set:
        raise SerializationError(
            f"trigger {trigger_name!r}: return annotation must not be a collection"
        )

    # Scalars: isinstance check.
    if inner in {str, int, float, bool}:
        if not isinstance(value, inner) or (inner is int and isinstance(value, bool)):
            raise SerializationError(
                f"trigger {trigger_name!r}: return value does not match annotation {annotation!r}"
            )
        return

        # Exact instance of the annotated class is already valid.
        if isinstance(inner, type) and isinstance(value, inner):
            return

        # Structured types: coerce via schema (dict / dataclass / pydantic / TypedDict).
        try:
            if dataclasses.is_dataclass(value) and not isinstance(value, type):
                candidate: Any = dump_value(value)
            elif _is_pydantic_instance(value):
                candidate = dump_value(value)
            elif isinstance(value, dict):
                candidate = value
            else:
                candidate = value
            coerce_value(annotation, candidate, context=f"trigger {trigger_name!r} return")
        except (ValidationError, SerializationError) as exc:
            raise SerializationError(
                f"trigger {trigger_name!r}: return value incompatible with annotation: {exc}"
            ) from exc


def _is_pydantic_instance(value: Any) -> bool:
    try:
        from pydantic import BaseModel
    except ImportError:
        return False
    return isinstance(value, BaseModel)
