"""Unit tests for the declarative curupira-sdk."""

from __future__ import annotations

import asyncio
import collections.abc
import inspect
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, TypedDict

import pytest
from curupira_sdk import Curupira, RegistrationError, SerializationError
from curupira_sdk.serialize import serialize_trigger_result
from curupira_sdk.signature import bind_arguments, build_trigger_spec, normalize_configuration

_FIXTURES = Path(__file__).resolve().parents[2] / "curupira-cli" / "tests" / "fixtures" / "protocol"


def test_trigger_decorator_without_parens_uses_kebab_case() -> None:
    app = Curupira(name="t", version="0")
    called = {"n": 0}

    @app.trigger
    def my_trigger(repo: str) -> dict[str, str] | None:
        called["n"] += 1
        return None

    assert list(app._triggers) == ["my-trigger"]
    assert app._triggers["my-trigger"].name == "my-trigger"
    assert called["n"] == 0
    assert my_trigger.__name__ == "my_trigger"


def test_trigger_alias_overrides_kebab_name() -> None:
    app = Curupira(name="t", version="0")

    @app.trigger(alias="issues")
    def github_issues(repo: str) -> None:
        return None

    assert list(app._triggers) == ["issues"]
    assert app._triggers["issues"].name == "issues"


def test_duplicate_trigger_name_raises() -> None:
    app = Curupira(name="t", version="0")

    @app.trigger
    def dup(repo: str) -> None:
        return None

    with pytest.raises(RegistrationError, match="duplicate"):

        @app.trigger
        def dup(repo: str) -> None:
            return None


def test_sync_and_async_registration() -> None:
    app = Curupira(name="t", version="0")

    @app.trigger
    def sync_one(x: str) -> None:
        return None

    @app.trigger
    async def async_one(x: str) -> None:
        return None

    assert app._triggers["sync-one"].is_async is False
    assert app._triggers["async-one"].is_async is True


def test_rejects_varargs_and_positional_only() -> None:
    def bad_args(*args: str) -> None:
        return None

    def bad_kwargs(**kwargs: str) -> None:
        return None

    def bad_pos(repo: str, /) -> None:
        return None

    with pytest.raises(RegistrationError, match=r"\*args"):
        build_trigger_spec(bad_args)
    with pytest.raises(RegistrationError, match=r"\*\*kwargs"):
        build_trigger_spec(bad_kwargs)
    with pytest.raises(RegistrationError, match="positional-only"):
        build_trigger_spec(bad_pos)


def test_rejects_collection_return_annotation() -> None:
    def many(repo: str) -> list[dict[str, str]]:
        return []

    with pytest.raises(RegistrationError, match="collection"):
        build_trigger_spec(many)


def test_schema_required_optional_defaults() -> None:
    def github_issues(
        repo: str,
        labels: list[str] | None = None,
        state: str = "open",
        limit: int = 50,
    ) -> dict[str, Any] | None:
        return None

    spec = build_trigger_spec(github_issues)
    assert spec.name == "github-issues"
    assert spec.schema["required"] == ["repo"]
    assert spec.schema["properties"]["state"]["default"] == "open"
    assert spec.schema["properties"]["limit"]["default"] == 50
    normalized = normalize_configuration(spec, {"repo": "acme/api"})
    assert normalized["state"] == "open"
    assert normalized["labels"] is None
    assert normalized["limit"] == 50


def test_unknown_and_invalid_parameters() -> None:
    def t(repo: str) -> None:
        return None

    spec = build_trigger_spec(t)
    with pytest.raises(Exception, match="unknown parameters"):
        bind_arguments(spec, {"repo": "a/b", "nope": 1})
    with pytest.raises(Exception, match="expected string"):
        bind_arguments(spec, {"repo": 1})


def test_core_field_name_conflict() -> None:
    def bad(repository: str) -> None:
        return None

    with pytest.raises(RegistrationError, match="conflicts with a core"):
        build_trigger_spec(bad)


@dataclass
class Issue:
    number: int
    title: str
    url: str


class IssueDict(TypedDict):
    number: int
    title: str
    url: str


class Bag(collections.abc.Mapping[str, Any]):
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Any:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


class Dup(collections.abc.Mapping[str, str]):
    def __getitem__(self, key: str) -> str:
        return "1"

    def __iter__(self) -> Any:
        return iter(("a", "a"))

    def __len__(self) -> int:
        return 2


def _pairs(value: Any, annotation: Any = Any) -> list[dict[str, str]] | None:
    return serialize_trigger_result(value, annotation, trigger_name="t")


def test_none_is_protocol_null_and_empty_mapping_is_empty_list() -> None:
    assert _pairs(None, Issue | None) is None
    assert _pairs({}, dict[str, Any] | None) == []


def test_serialize_dataclass_mapping_and_typed_dict() -> None:
    pairs = _pairs(Issue(1, "t", "http://x"), Issue | None)
    assert pairs == [
        {"key": "number", "value": "1"},
        {"key": "title", "value": "t"},
        {"key": "url", "value": "http://x"},
    ]
    assert _pairs({"number": 9, "title": "hi", "url": "u"}, IssueDict | None) == [
        {"key": "number", "value": "9"},
        {"key": "title", "value": "hi"},
        {"key": "url", "value": "u"},
    ]
    assert _pairs(Bag({"note": "ok"}), Any) == [{"key": "note", "value": "ok"}]


def test_serialize_value_conversions() -> None:
    @dataclass
    class Nested:
        z: int
        a: str | None

    pairs = _pairs(
        {
            "text": "as-is",
            "flag": False,
            "count": 1,
            "ratio": 1.0,
            "empty": None,
            "labels": ["bug", "p1"],
            "meta": {"b": 1, "a": "x"},
            "child": Nested(2, None),
        },
        Any,
    )
    assert pairs == [
        {"key": "text", "value": "as-is"},
        {"key": "flag", "value": "false"},
        {"key": "count", "value": "1"},
        {"key": "ratio", "value": "1.0"},
        {"key": "empty", "value": "null"},
        {"key": "labels", "value": '["bug","p1"]'},
        {"key": "meta", "value": '{"a":"x","b":1}'},
        {"key": "child", "value": '{"a":null,"z":2}'},
    ]


def test_serialize_rejects_incompatible_returns() -> None:
    with pytest.raises(SerializationError, match="collection"):
        _pairs([{"key": "a", "value": "b"}], Any)
    with pytest.raises(SerializationError, match="collection"):
        _pairs(({"a": "b"},), Any)

    def gen():
        yield {"a": "b"}

    with pytest.raises(SerializationError, match="collection"):
        _pairs(gen(), Any)
    with pytest.raises(SerializationError, match="not"):
        _pairs(42, int | None)
    with pytest.raises(SerializationError, match="not a string"):
        _pairs({1: "a"}, Any)
    with pytest.raises(SerializationError, match="not a string"):
        _pairs({"outer": {1: "a"}}, Any)
    with pytest.raises(SerializationError, match="placeholder"):
        _pairs({"": "a"}, Any)
    with pytest.raises(SerializationError, match="placeholder"):
        _pairs({"a}": "b"}, Any)
    with pytest.raises(SerializationError, match="placeholder"):
        _pairs({"${a": "b"}, Any)
    with pytest.raises(SerializationError, match="duplicate"):
        _pairs(Dup(), Any)
    with pytest.raises(SerializationError, match="not serializable"):
        _pairs({"blob": b"hi"}, Any)
    with pytest.raises(SerializationError, match="not serializable"):
        _pairs({"when": datetime(2020, 1, 1)}, Any)
    with pytest.raises(SerializationError, match="not serializable"):
        _pairs({"tags": {"a", "b"}}, Any)
    with pytest.raises(SerializationError, match="non-finite"):
        _pairs({"n": float("nan")}, Any)


def test_serialize_unannotated_runtime() -> None:
    pairs = _pairs({"note": "a"}, Any)
    assert pairs == [{"key": "note", "value": "a"}]


def test_serialize_matches_shared_protocol_fixtures() -> None:
    payload = {
        "issue-number": 42,
        "ready": True,
        "count": 1,
        "ratio": 1.0,
        "note": None,
        "labels": ["bug", "p1"],
        "meta": {"b": 1, "a": "x"},
    }
    assert {"values": _pairs(payload, dict[str, Any] | None)} == json.loads(
        (_FIXTURES / "poll-values.json").read_text()
    )
    assert {"values": _pairs(None, dict[str, Any] | None)} == json.loads(
        (_FIXTURES / "poll-null.json").read_text()
    )
    assert {"values": _pairs({}, dict[str, Any] | None)} == json.loads(
        (_FIXTURES / "poll-empty.json").read_text()
    )


def test_pydantic_optional_dependency() -> None:
    pydantic = pytest.importorskip("pydantic")

    class Model(pydantic.BaseModel):
        note: str
        ready: bool

    def t(repo: str) -> Model | None:
        return None

    # The module uses postponed annotations, so the local `Model` cannot be resolved from a string.
    t.__annotations__ = {"repo": str, "return": Model | None}
    spec = build_trigger_spec(t)
    assert spec.prompt_fields == ("note", "ready")
    pairs = serialize_trigger_result(Model(note="x", ready=True), Model | None, trigger_name="t")
    assert pairs == [
        {"key": "note", "value": "x"},
        {"key": "ready", "value": "true"},
    ]


def test_pydantic_missing_dependency_message(monkeypatch: pytest.MonkeyPatch) -> None:
    import curupira_sdk.types as types_mod

    class FakeBase:
        pass

    FakeBase.__name__ = "BaseModel"

    class Model(FakeBase):
        pass

    monkeypatch.setattr(types_mod, "_is_pydantic_model", lambda _annotation: False)

    def boom(_context: str) -> Any:
        raise RegistrationError(
            "ctx: Pydantic models require the optional dependency "
            "`curupira-sdk[pydantic]` (pydantic>=2,<3)"
        )

    monkeypatch.setattr(types_mod, "_require_pydantic", boom)

    with pytest.raises(RegistrationError, match="optional dependency"):
        types_mod.type_to_json_schema(Model, context="ctx")


def test_invoke_sync_and_async() -> None:
    from curupira_sdk.runtime import invoke

    def sync_fn(x: int) -> int:
        return x + 1

    async def async_fn(x: int) -> int:
        await asyncio.sleep(0)
        return x + 2

    assert invoke(sync_fn, {"x": 1}, is_async=False) == 2
    assert invoke(async_fn, {"x": 1}, is_async=True) == 3


def test_poll_handler_none_vs_pairs_without_polling_params() -> None:
    app = Curupira(name="t", version="0")
    seen: dict[str, Any] = {}

    @app.trigger
    def once(repo: str) -> Issue | None:
        seen["repo"] = repo
        if repo == "empty/repo":
            return None
        return Issue(7, "title", "http://example")

    none_result = app._handle_poll(
        {
            "trigger_type": "once",
            "automation": {"repo": "empty/repo"},
            "preview": False,
            "limit": 1,
        }
    )
    assert none_result == {"values": None}
    assert seen["repo"] == "empty/repo"

    item_result = app._handle_poll(
        {"trigger_type": "once", "automation": {"repo": "a/b"}, "preview": True, "limit": 9}
    )
    assert item_result == {
        "values": [
            {"key": "number", "value": "7"},
            {"key": "title", "value": "title"},
            {"key": "url", "value": "http://example"},
        ]
    }
    assert "preview" not in seen
    assert "limit" not in seen

    err = app._handle_validate({"trigger_type": "once", "configuration": {}})
    assert err["ok"] is False


def test_validate_applies_defaults() -> None:
    app = Curupira(name="t", version="0")

    @app.trigger
    def t(repo: str, state: str = "open") -> None:
        return None

    result = app._handle_validate(
        {"trigger_type": "t", "configuration": {"repo": "a/b", "repository": "api", "prompt": "x"}}
    )
    assert result["ok"] is True
    assert result["configuration"]["state"] == "open"


def test_signature_preserved() -> None:
    app = Curupira(name="t", version="0")

    @app.trigger
    def named(repo: str, limit: int = 1) -> None:
        """doc"""
        return

    assert named.__name__ == "named"
    assert named.__doc__ == "doc"
    assert inspect.signature(named).parameters["limit"].default == 1
