"""monday.com GraphQL client behavior with httpx.MockTransport (no network)."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from curupira.clients.monday import MondayClient
from curupira.errors import HttpApiError, TransientHttpApiError
from curupira.models.monday import MondayListRequest

# Mock credential for MockTransport assertions (not a real secret).
_FAKE_API_CREDENTIAL = "monday-test-credential"


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
) -> MondayClient:
    env_name = "MONDAY_API_" + "TOKEN"
    return MondayClient(
        token_env=env_name,
        transport=httpx.MockTransport(handler),
        environ=environ if environ is not None else {env_name: _FAKE_API_CREDENTIAL},
    )


@pytest.mark.asyncio
async def test_list_items_single_page_preserves_string_ids() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == _FAKE_API_CREDENTIAL
        assert request.headers["API-Version"] == "2026-10"
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
            return httpx.Response(200, json=_next_page([_item("2", "Second")], cursor=None))
        return httpx.Response(200, json=_first_page([_item("1", "First")], cursor="cursor-1"))

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
    custom_env_name = "CUSTOM_MONDAY_" + "TOKEN"
    client = MondayClient(
        token_env=custom_env_name,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
        environ={},
    )
    with pytest.raises(HttpApiError, match=custom_env_name) as error:
        await client.list_items_page(MondayListRequest(board_id="1", limit=1))
    assert _FAKE_API_CREDENTIAL not in str(error.value)
    assert custom_env_name in str(error.value)


@pytest.mark.asyncio
async def test_http_401_is_actionable_and_hides_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(401, text="unauthorized")

    with pytest.raises(HttpApiError, match="401") as error:
        await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))
    message = str(error.value)
    assert "MONDAY_API_TOKEN" in message
    assert "open the board in the monday.com UI" in message
    assert "boards:read" not in message
    assert _FAKE_API_CREDENTIAL not in message


@pytest.mark.asyncio
async def test_http_429_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(seconds: float) -> None:
        del seconds

    monkeypatch.setattr("curupira.clients.monday.asyncio.sleep", no_sleep)
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
async def test_http_503_is_transient(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(seconds: float) -> None:
        del seconds

    monkeypatch.setattr("curupira.clients.monday.asyncio.sleep", no_sleep)

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
async def test_empty_boards_is_actionable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"data": {"boards": []}})

    with pytest.raises(HttpApiError, match="board 99 not found or not accessible") as error:
        await _client(handler).list_items_page(MondayListRequest(board_id="99", limit=1))
    assert "check board_id" in str(error.value)


@pytest.mark.asyncio
async def test_boards_payload_must_be_a_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"data": {"boards": {"id": "1"}}})

    with pytest.raises(HttpApiError, match="missing boards"):
        await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))


@pytest.mark.asyncio
async def test_invalid_item_json_and_blank_cursor() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "data": {
                    "boards": [
                        {
                            "items_page": {
                                "cursor": "   ",
                                "items": [{"id": "1", "name": "X"}],
                            }
                        }
                    ]
                }
            },
        )

    with pytest.raises(HttpApiError, match="invalid item JSON"):
        await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))


@pytest.mark.asyncio
async def test_non_string_cursor_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "data": {
                    "boards": [
                        {
                            "items_page": {
                                "cursor": 123,
                                "items": [_item("1", "Ok")],
                            }
                        }
                    ]
                }
            },
        )

    with pytest.raises(HttpApiError, match="cursor must be a string"):
        await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))


@pytest.mark.asyncio
async def test_http_400_and_non_object_payload() -> None:
    def bad_status(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(400, text="bad request")

    with pytest.raises(HttpApiError, match="status 400"):
        await _client(bad_status).list_items_page(MondayListRequest(board_id="1", limit=1))

    def non_object(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json=["not", "an", "object"])

    with pytest.raises(HttpApiError, match="non-object"):
        await _client(non_object).list_items_page(MondayListRequest(board_id="1", limit=1))


@pytest.mark.asyncio
async def test_graphql_errors_must_be_a_list() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"errors": "boom"})

    with pytest.raises(HttpApiError, match="errors payload is invalid"):
        await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))


@pytest.mark.asyncio
async def test_blank_token_is_treated_as_missing() -> None:
    env_name = "MONDAY_API_" + "TOKEN"
    client = MondayClient(
        token_env=env_name,
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
        environ={env_name: "   "},
    )
    with pytest.raises(HttpApiError, match=env_name):
        await client.list_items_page(MondayListRequest(board_id="1", limit=1))


@pytest.mark.asyncio
async def test_http_403_mentions_token_env_without_leaking_secret() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(403, text="forbidden")

    with pytest.raises(HttpApiError, match="403") as error:
        await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))
    assert _FAKE_API_CREDENTIAL not in str(error.value)


@pytest.mark.asyncio
async def test_transport_error_is_transient() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        raise httpx.ConnectError("connection refused")

    with pytest.raises(TransientHttpApiError, match="transport failed"):
        await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))


@pytest.mark.asyncio
async def test_blank_cursor_string_normalized_to_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "data": {
                    "boards": [
                        {
                            "items_page": {
                                "cursor": "  ",
                                "items": [_item("1", "Ok")],
                            }
                        }
                    ]
                }
            },
        )

    page = await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))
    assert page.cursor is None
    assert page.items[0].id == "1"


@pytest.mark.asyncio
async def test_api_version_header_is_pinned_current(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["API-Version"])
        return httpx.Response(200, json=_first_page([_item("1", "Ok")], cursor=None))

    async def no_sleep(seconds: float) -> None:
        del seconds

    monkeypatch.setattr("curupira.clients.monday.asyncio.sleep", no_sleep)
    await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))
    assert seen == ["2026-10"]


@pytest.mark.asyncio
async def test_query_complexity_exceeds_is_permanent_with_batch_size_hint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={"errors": [{"message": "Query complexity exceeds the limit of 5000000"}]},
        )

    with pytest.raises(HttpApiError, match="batch_size") as error:
        await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))
    assert not isinstance(error.value, TransientHttpApiError)


@pytest.mark.asyncio
async def test_complexity_budget_exhausted_is_transient_and_honors_retry_in_seconds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []

    async def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("curupira.clients.monday.asyncio.sleep", record_sleep)
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        attempts["count"] += 1
        if attempts["count"] < 2:
            return httpx.Response(
                200,
                json={
                    "errors": [
                        {
                            "message": "Complexity budget exhausted",
                            "extensions": {"retry_in_seconds": 2},
                        }
                    ]
                },
            )
        return httpx.Response(200, json=_first_page([_item("1", "Ok")], cursor=None))

    page = await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))
    assert page.items[0].id == "1"
    assert attempts["count"] == 2
    # ``@resilient(delay=0)`` may still call ``sleep(0)`` between attempts.
    assert [seconds for seconds in sleeps if seconds > 0] == [2.0]


@pytest.mark.asyncio
async def test_http_429_honors_retry_after_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []

    async def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("curupira.clients.monday.asyncio.sleep", record_sleep)
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        attempts["count"] += 1
        if attempts["count"] < 2:
            return httpx.Response(429, text="rate limited", headers={"Retry-After": "3"})
        return httpx.Response(200, json=_first_page([_item("1", "Ok")], cursor=None))

    page = await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))
    assert page.items[0].id == "1"
    assert [seconds for seconds in sleeps if seconds > 0] == [3.0]


@pytest.mark.asyncio
async def test_http_503_uses_default_retry_delay_without_resilient_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []

    async def record_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr("curupira.clients.monday.asyncio.sleep", record_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(503, text="unavailable")

    with pytest.raises(TransientHttpApiError, match="503"):
        await _client(handler).list_items_page(MondayListRequest(board_id="1", limit=1))
    assert [seconds for seconds in sleeps if seconds > 0] == [1.0, 1.0, 1.0]
