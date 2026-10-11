"""monday.com GraphQL client behavior with httpx.MockTransport (no network)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from curupira.clients.monday import MondayClient
from curupira.errors import HttpApiError, TransientHttpApiError
from curupira.models.monday import MondayListRequest

_TOKEN = "monday-test-token-not-for-production"


def _item(
    item_id: str | int,
    name: str,
    *,
    state: str = "active",
    group_id: str = "topics",
    group_title: str = "Topics",
    columns: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "name": name,
        "url": f"https://acme.monday.com/boards/1/pulses/{item_id}",
        "state": state,
        "group": {"id": group_id, "title": group_title},
        "column_values": columns or [{"id": "status", "text": "Done"}],
    }


def _first_page(items: list[dict[str, Any]], cursor: str | None = None) -> dict[str, Any]:
    return {"data": {"boards": [{"items_page": {"cursor": cursor, "items": items}}]}}


def _next_page(items: list[dict[str, Any]], cursor: str | None = None) -> dict[str, Any]:
    return {"data": {"next_items_page": {"cursor": cursor, "items": items}}}


def _client(
    handler: Any,
    *,
    environ: dict[str, str] | None = None,
    token_env: str = "MONDAY_API_TOKEN",
) -> MondayClient:
    return MondayClient(
        token_env=token_env,
        transport=httpx.MockTransport(handler),
        environ=environ if environ is not None else {"MONDAY_API_TOKEN": _TOKEN},
    )


@pytest.mark.asyncio
async def test_list_items_single_page_preserves_string_ids() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == _TOKEN
        assert "Bearer" not in request.headers["Authorization"]
        body = json.loads(request.content.decode())
        assert body["variables"]["boardIds"] == ["1234567890"]
        assert body["variables"]["queryParams"] is None
        return httpx.Response(200, json=_first_page([_item(9876543210, "Ship")], cursor=None))

    page = await _client(handler).list_items_page(
        MondayListRequest(board_id="1234567890", limit=10)
    )

    assert page.cursor is None
    assert len(page.items) == 1
    assert page.items[0].id == "9876543210"
    assert page.items[0].name == "Ship"


@pytest.mark.asyncio
async def test_empty_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json=_first_page([], cursor=None))

    page = await _client(handler).list_items_page(
        MondayListRequest(board_id="1234567890", limit=10)
    )
    assert page.items == ()
    assert page.cursor is None


@pytest.mark.asyncio
async def test_two_pages_by_cursor() -> None:
    calls: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        calls.append(body)
        if "next_items_page" in body["query"]:
            assert body["variables"]["cursor"] == "cursor-1"
            return httpx.Response(
                200, json=_next_page([_item("2", "Second")], cursor=None)
            )
        return httpx.Response(
            200, json=_first_page([_item("1", "First")], cursor="cursor-1")
        )

    client = _client(handler)
    first = await client.list_items_page(MondayListRequest(board_id="1", limit=1))
    second = await client.list_items_page(
        MondayListRequest(board_id="1", cursor="cursor-1", limit=1)
    )

    assert [item.id for item in first.items] == ["1"]
    assert first.cursor == "cursor-1"
    assert [item.id for item in second.items] == ["2"]
    assert second.cursor is None
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_group_ids_filter_uses_query_params() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body["variables"]["queryParams"] == {
            "rules": [
                {
                    "column_id": "group",
                    "compare_value": ["topics", "done"],
                    "operator": "any_of",
                }
            ]
        }
        return httpx.Response(200, json=_first_page([_item("1", "Filtered")], cursor=None))

    page = await _client(handler).list_items_page(
        MondayListRequest(board_id="1", group_ids=("topics", "done"), limit=5)
    )
    assert page.items[0].id == "1"


@pytest.mark.asyncio
async def test_missing_token_names_environment_variable() -> None:
    client = MondayClient(
        token_env="CUSTOM_MONDAY_TOKEN",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
        environ={},
    )
    with pytest.raises(HttpApiError, match="CUSTOM_MONDAY_TOKEN") as error:
        await client.list_items_page(MondayListRequest(board_id="1", limit=1))
    assert _TOKEN not in str(error.value)
    assert "CUSTOM_MONDAY_TOKEN" in str(error.value)


@pytest.mark.asyncio
async def test_http_401_is_actionable_and_hides_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(401, text="unauthorized")

    with pytest.raises(HttpApiError, match="401") as error:
        await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))
    message = str(error.value)
    assert "MONDAY_API_TOKEN" in message
    assert _TOKEN not in message


@pytest.mark.asyncio
async def test_http_429_retries_then_succeeds() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        attempts["count"] += 1
        if attempts["count"] < 2:
            return httpx.Response(429, text="rate limited")
        return httpx.Response(200, json=_first_page([_item("1", "Ok")], cursor=None))

    page = await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))
    assert page.items[0].id == "1"
    assert attempts["count"] == 2


@pytest.mark.asyncio
async def test_http_503_is_transient() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(503, text="unavailable")

    with pytest.raises(TransientHttpApiError, match="503"):
        await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))


@pytest.mark.asyncio
async def test_graphql_errors_array() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={"errors": [{"message": "Board not found"}, {"message": "bad id"}]},
        )

    with pytest.raises(HttpApiError, match="Board not found") as error:
        await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))
    assert "bad id" in str(error.value)


@pytest.mark.asyncio
async def test_invalid_json_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, text="not-json", headers={"content-type": "text/plain"})

    with pytest.raises(HttpApiError, match="non-JSON"):
        await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))


@pytest.mark.asyncio
async def test_missing_data_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"errors": None})

    with pytest.raises(HttpApiError, match="missing data"):
        await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))


@pytest.mark.asyncio
async def test_unexpected_boards_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"data": {"boards": []}})

    with pytest.raises(HttpApiError, match="missing boards"):
        await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))
