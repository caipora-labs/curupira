"""Function signature introspection for trigger parameters."""

from __future__ import annotations

import inspect
import typing
from dataclasses import dataclass
from typing import Any, get_type_hints

from .errors import RegistrationError, ValidationError
from .types import coerce_value, is_collection_type, prompt_fields_for_return, type_to_json_schema

# Core automation fields owned by the Rust host — not function parameters.
CORE_CONFIG_KEYS = frozenset(
    {
        "trigger_type",
        "repository",
        "prompt",
        "profile",
        "checkout",
    }
)


@dataclass(frozen=True, slots=True)
class ParameterSpec:
    name: str
    annotation: Any
    required: bool
    default: Any
    has_default: bool


@dataclass(frozen=True, slots=True)
class TriggerSpec:
    name: str
    func: Any
    is_async: bool
    parameters: tuple[ParameterSpec, ...]
    return_annotation: Any
    prompt_fields: tuple[str, ...]
    schema: dict[str, Any]


def to_kebab_case(name: str) -> str:
    """Convert a Python identifier to kebab-case (``github_issues`` → ``github-issues``)."""
    if not name:
        raise RegistrationError("trigger name must not be empty")
    parts = [part for part in name.replace("-", "_").split("_") if part]
    if not parts:
        raise RegistrationError(f"trigger name {name!r} is not a valid identifier")
    return "-".join(part.lower() for part in parts)


def validate_trigger_local_name(name: str) -> str:
    """Accept a kebab-case local trigger name (no slash; used inside an extension)."""
    if not name:
        raise RegistrationError("trigger name must not be empty")
    if "/" in name:
        raise RegistrationError(
            f"trigger name {name!r} must not contain '/'; "
            "the host prefixes the [plugins.<alias>] registration name"
        )
    if name.startswith("-") or name.endswith("-") or "--" in name:
        raise RegistrationError(f"trigger name {name!r} is not valid kebab-case")
    if not all(c.isalnum() or c == "-" for c in name):
        raise RegistrationError(f"trigger name {name!r} is not valid kebab-case")
    if not any(c.isalpha() for c in name):
        raise RegistrationError(f"trigger name {name!r} is not valid kebab-case")
    return name


def build_trigger_spec(func: Any, *, name: str | None = None) -> TriggerSpec:
    """Introspect a trigger function without calling it.

    When ``name`` is omitted, the local trigger name is the kebab-case form of
    ``func.__name__``. Pass ``name`` (or ``@app.trigger(alias=...)``) to override.
    """
    if not callable(func):
        raise RegistrationError("trigger must be a callable")
    func_name = func.__name__
    if not func_name.isidentifier():
        raise RegistrationError(f"trigger function {func_name!r} is not a valid identifier")
    local_name = validate_trigger_local_name(name if name is not None else to_kebab_case(func_name))

    signature = inspect.signature(func)
    try:
        hints = get_type_hints(func, include_extras=True)
    except Exception as exc:
        raise RegistrationError(f"trigger {local_name!r}: cannot resolve type hints: {exc}") from exc

    parameters: list[ParameterSpec] = []
    for param_name, param in signature.parameters.items():
        if param.kind is inspect.Parameter.VAR_POSITIONAL:
            raise RegistrationError(f"trigger {local_name!r}: *args is not supported")
        if param.kind is inspect.Parameter.VAR_KEYWORD:
            raise RegistrationError(f"trigger {local_name!r}: **kwargs is not supported")
        if param.kind is inspect.Parameter.POSITIONAL_ONLY:
            raise RegistrationError(
                f"trigger {local_name!r}: positional-only parameter {param_name!r} "
                "is not supported"
            )
        if param.kind not in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            raise RegistrationError(
                f"trigger {local_name!r}: unsupported parameter kind for {param_name!r}"
            )
        if param_name in CORE_CONFIG_KEYS:
            raise RegistrationError(
                f"trigger {local_name!r}: parameter {param_name!r} conflicts with a core "
                "automation field; use a different name (for example `repo`)"
            )
        if param.annotation is inspect.Parameter.empty:
            raise RegistrationError(
                f"trigger {local_name!r}: parameter {param_name!r} requires a type annotation"
            )
        annotation = hints.get(param_name, param.annotation)
        context = f"trigger {local_name!r} parameter {param_name!r}"
        # Ensure the type is representable (raises RegistrationError if not).
        type_to_json_schema(annotation, context=context)
        has_default = param.default is not inspect.Parameter.empty
        parameters.append(
            ParameterSpec(
                name=param_name,
                annotation=annotation,
                required=not has_default,
                default=param.default if has_default else None,
                has_default=has_default,
            )
        )

    return_annotation = hints.get("return", signature.return_annotation)
    if return_annotation is inspect.Signature.empty:
        return_annotation = typing.Any
    if is_collection_type(return_annotation):
        raise RegistrationError(
            f"trigger {local_name!r}: return type must be a single item or None, "
            "not a collection"
        )

    schema = _parameters_schema(local_name, parameters)
    prompt_fields = tuple(prompt_fields_for_return(return_annotation))
    return TriggerSpec(
        name=local_name,
        func=func,
        is_async=inspect.iscoroutinefunction(func),
        parameters=tuple(parameters),
        return_annotation=return_annotation,
        prompt_fields=prompt_fields,
        schema=schema,
    )


def _parameters_schema(trigger_name: str, parameters: list[ParameterSpec]) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param in parameters:
        context = f"trigger {trigger_name!r} parameter {param.name!r}"
        prop = type_to_json_schema(param.annotation, context=context)
        if param.has_default:
            from .errors import SerializationError
            from .types import dump_value

            try:
                prop = {**prop, "default": dump_value(param.default)}
            except SerializationError:
                pass
        properties[param.name] = prop
        if param.required:
            required.append(param.name)
    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


def bind_arguments(spec: TriggerSpec, configuration: dict[str, Any]) -> dict[str, Any]:
    """Extract and coerce function kwargs from an automation configuration."""
    param_names = {p.name for p in spec.parameters}
    extras = sorted(
        key for key in configuration if key not in CORE_CONFIG_KEYS and key not in param_names
    )
    if extras:
        raise ValidationError(f"trigger {spec.name!r}: unknown parameters {extras}")

    kwargs: dict[str, Any] = {}
    for param in spec.parameters:
        if param.name in configuration:
            kwargs[param.name] = coerce_value(
                param.annotation,
                configuration[param.name],
                context=f"trigger {spec.name!r} parameter {param.name!r}",
            )
        elif param.has_default:
            kwargs[param.name] = param.default
        else:
            raise ValidationError(
                f"trigger {spec.name!r}: missing required parameter {param.name!r}"
            )
    return kwargs


def normalize_configuration(spec: TriggerSpec, configuration: dict[str, Any]) -> dict[str, Any]:
    """Validate trigger params and return a full configuration with defaults applied."""
    kwargs = bind_arguments(spec, configuration)
    normalized = dict(configuration)
    for param in spec.parameters:
        normalized[param.name] = kwargs[param.name]
    return normalized
