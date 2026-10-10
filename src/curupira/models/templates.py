"""Flatten Pydantic models into string.Template placeholder values."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import cast

from pydantic import BaseModel


def flatten_for_template(model: BaseModel) -> dict[str, str]:
    """Convert a Pydantic model into flat string placeholders for ``string.Template``.

    Scalars become strings, ``None`` becomes ``""``, booleans become ``true``/``false``,
    and lists, dicts, or nested models become compact JSON.
    """
    return {key: _stringify(value) for key, value in model.model_dump(mode="python").items()}


def common_prompt_context(
    *,
    repo: str,
    automation_id: str,
    task_type: str,
    task_number: str,
    task_title: str,
    task_url: str,
    item: BaseModel,
    repository: str | None = None,
) -> dict[str, str]:
    """Build the shared prompt context plus flattened item fields.

    ``task_body`` is taken from the item when it exposes ``body`` or a ``*_body`` field.
    """
    item_context = flatten_for_template(item)
    return {
        "repo": repo,
        "repository": repository if repository is not None else repo,
        "automation_id": automation_id,
        "task_type": task_type,
        "task_number": task_number,
        "task_title": task_title,
        "task_body": _body_from_item(item_context),
        "task_url": task_url,
        **item_context,
    }


def _body_from_item(item_context: Mapping[str, str]) -> str:
    if "body" in item_context:
        return item_context["body"]
    for key, value in item_context.items():
        if key.endswith("_body"):
            return value
    return ""


def _stringify(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return str(value)
    if isinstance(value, BaseModel):
        return json.dumps(value.model_dump(mode="python"), separators=(",", ":"), default=str)
    if isinstance(value, Mapping):
        payload = dict(cast(Mapping[object, object], value))
        return json.dumps(payload, separators=(",", ":"), default=str)
    if isinstance(value, (list, tuple)):
        return json.dumps(list(value), separators=(",", ":"), default=str)
    return str(value)
