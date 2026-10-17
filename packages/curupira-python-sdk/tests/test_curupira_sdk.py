"""Unit tests for the declarative curupira-sdk."""

from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass
from typing import Any, TypedDict

import pytest
from curupira_sdk import Curupira, RegistrationError, SerializationError
from curupira_sdk.serialize import serialize_trigger_result
from curupira_sdk.signature import bind_arguments, build_trigger_spec, normalize_configuration


def test_trigger_decorator_without_parens_uses_function_name() -> None:
    app = Curupira(name="t", version="0")
    called = {"n": 0}

    @app.trigger
    def my_trigger(repo: str) -> dict[str, str] | None:
        called["n"] += 1
        return None

    assert list(app._triggers) == ["my_trigger"]
    assert app._triggers["my_trigger"].name == "my_trigger"
    assert called["n"] == 0
    assert my_trigger.__name__ == "my_trigger"


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

    assert app._triggers["sync_one"].is_async is False
    assert app._triggers["async_one"].is_async is True


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
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(self.number)


class IssueDict(TypedDict):
    id: str
    title: str
    url: str


def test_serialize_dataclass_and_none() -> None:
    env = serialize_trigger_result(
        Issue(1, "t", "http://x"), Issue | None, trigger_name="github_issues"
    )
    assert env is not None
    assert env["id"] == "1"
    assert env["item"]["title"] == "t"
    assert serialize_trigger_result(None, Issue | None, trigger_name="github_issues") is None


def test_serialize_typed_dict() -> None:
    env = serialize_trigger_result(
        {"id": "9", "title": "hi", "url": "u"},
        IssueDict | None,
        trigger_name="t",
    )
    assert env is not None
    assert env["id"] == "9"


def test_serialize_rejects_list_tuple_generator() -> None:
    with pytest.raises(SerializationError, match="collection"):
        serialize_trigger_result([{"id": "1"}], Any, trigger_name="t")
    with pytest.raises(SerializationError, match="collection"):
        serialize_trigger_result(({"id": "1"},), Any, trigger_name="t")

    def gen():
        yield {"id": "1"}

    with pytest.raises(SerializationError, match="collection"):
        serialize_trigger_result(gen(), Any, trigger_name="t")


def test_serialize_unannotated_runtime() -> None:
    env = serialize_trigger_result({"id": "a", "title": "t"}, Any, trigger_name="t")
    assert env is not None
    assert env["id"] == "a"


def test_serialize_scalar() -> None:
    env = serialize_trigger_result(42, int | None, trigger_name="t")
    assert env is not None
    assert env["id"] == "42"
    assert env["item"]["value"] == 42


def test_pydantic_optional_dependency() -> None:
    pydantic = pytest.importorskip("pydantic")

    class Model(pydantic.BaseModel):
        id: str
        title: str

    def t(repo: str) -> Model | None:
        return None

    # The module uses postponed annotations, so the local `Model` cannot be resolved from a string.
    t.__annotations__ = {"repo": str, "return": Model | None}
    spec = build_trigger_spec(t)
    assert "id" in spec.prompt_fields
    env = serialize_trigger_result(Model(id="1", title="x"), Model | None, trigger_name="t")
    assert env is not None
    assert env["title"] == "x"


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


def test_poll_handler_none_vs_item() -> None:
    app = Curupira(name="t", version="0")

    @app.trigger
    def once(repo: str) -> Issue | None:
        if repo == "empty/repo":
            return None
        return Issue(7, "title", "http://example")

    none_result = app._handle_poll(
        {"trigger_type": "once", "automation": {"repo": "empty/repo"}, "preview": False, "limit": 1}
    )
    assert none_result == {"task": None}

    item_result = app._handle_poll(
        {"trigger_type": "once", "automation": {"repo": "a/b"}, "preview": False, "limit": 1}
    )
    assert item_result["task"]["id"] == "7"

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
