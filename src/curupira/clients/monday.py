"""Async monday.com GraphQL client for board item discovery."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Mapping
from typing import Any

import httpx
from pydantic import TypeAdapter, ValidationError
from pyresilience import RetryConfig, resilient

from curupira.errors import HttpApiError, TransientHttpApiError
from curupira.models.monday import MondayBoardItem, MondayItemsPage, MondayListRequest

_MONDAY_GRAPHQL_URL = "https://api.monday.com/v2"
# Current stable monday.com API version (see developer.monday.com API versioning).
_API_VERSION = "2026-07"
# Environment variable *name* for the personal API token (not a secret value).
_DEFAULT_TOKEN_ENV = "MONDAY_API_TOKEN"  # noqa: S105
_MAX_RETRY_AFTER_SECONDS = 60.0

_FIRST_PAGE_QUERY = """
query CurupiraMondayItems($boardIds: [ID!]!, $limit: Int!, $queryParams: ItemsQuery) {
  boards(ids: $boardIds) {
    items_page(limit: $limit, query_params: $queryParams) {
      cursor
      items {
        id
        name
        url
        state
        group {
          id
          title
        }
        column_values {
          id
          text
        }
      }
    }
  }
}
"""

_NEXT_PAGE_QUERY = """
query CurupiraMondayNextItems($cursor: String!, $limit: Int!) {
  next_items_page(cursor: $cursor, limit: $limit) {
    cursor
    items {
      id
      name
      url
      state
      group {
        id
        title
      }
      column_values {
        id
        text
      }
    }
  }
}
"""


class MondayClient:
    """List monday.com board items through the GraphQL API over ``httpx``."""

    def __init__(
        self,
        *,
        token_env: str = _DEFAULT_TOKEN_ENV,
        transport: httpx.AsyncBaseTransport | None = None,
        endpoint: str = _MONDAY_GRAPHQL_URL,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self._token_env = token_env
        self._transport = transport
        self._endpoint = endpoint
        self._environ = environ if environ is not None else os.environ

    async def list_items_page(self, request: MondayListRequest) -> MondayItemsPage:
        """Return one page of board items, optionally filtered by group IDs."""
        token = self._require_token()
        if request.cursor:
            body: dict[str, Any] = {
                "query": _NEXT_PAGE_QUERY,
                "variables": {"cursor": request.cursor, "limit": request.limit},
            }
        else:
            variables: dict[str, Any] = {
                "boardIds": [request.board_id],
                "limit": request.limit,
                "queryParams": None,
            }
            if request.group_ids is not None:
                variables["queryParams"] = {
                    "rules": [
                        {
                            "column_id": "group",
                            "compare_value": list(request.group_ids),
                            "operator": "any_of",
                        }
                    ]
                }
            body = {"query": _FIRST_PAGE_QUERY, "variables": variables}
        document = await self._post_resilient(token, body)
        raw_page = _page_from_response(
            document,
            has_cursor=bool(request.cursor),
            board_id=request.board_id,
        )
        try:
            items = TypeAdapter(list[MondayBoardItem]).validate_python(raw_page["items"])
        except ValidationError as error:
            raise HttpApiError(f"monday.com returned invalid item JSON: {error}") from error
        cursor = raw_page.get("cursor")
        if cursor is not None and not isinstance(cursor, str):
            raise HttpApiError("monday.com GraphQL cursor must be a string or null")
        if isinstance(cursor, str) and not cursor.strip():
            cursor = None
        return MondayItemsPage(items=tuple(items), cursor=cursor)

    def _require_token(self) -> str:
        """Read the API token from the configured environment variable."""
        token = self._environ.get(self._token_env)
        if token is None or not token.strip():
            raise HttpApiError(
                f"monday.com API token is missing; set the {self._token_env} environment "
                "variable to a personal monday.com API token "
                "(Developer Center → API token)"
            )
        return token.strip()

    @resilient(
        retry=RetryConfig(
            max_attempts=3,
            delay=1.0,
            backoff_factor=2.0,
            max_delay=5.0,
            jitter=True,
            retry_on=(TransientHttpApiError,),
        )
    )
    async def _post_resilient(self, token: str, body: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": token,
            "Content-Type": "application/json",
            "API-Version": _API_VERSION,
        }
        async with httpx.AsyncClient(transport=self._transport, timeout=30.0) as client:
            try:
                response = await client.post(self._endpoint, headers=headers, json=body)
            except httpx.TransportError as error:
                raise TransientHttpApiError(
                    f"monday.com GraphQL transport failed: {error}"
                ) from error
        if response.status_code in {429, 502, 503, 504} or response.status_code >= 500:
            retry_after = _retry_after_from_response(response)
            await _maybe_sleep_retry_after(retry_after)
            raise TransientHttpApiError(
                f"monday.com GraphQL temporarily failed with status {response.status_code}",
                retry_after_seconds=retry_after,
            )
        if response.status_code in {401, 403}:
            raise HttpApiError(
                f"monday.com GraphQL authentication failed with status "
                f"{response.status_code}; check that {self._token_env} holds a valid "
                "personal API token and that its owner can open the board in the "
                "monday.com UI"
            )
        if response.status_code >= 400:
            raise HttpApiError(f"monday.com GraphQL failed with status {response.status_code}")
        try:
            document = response.json()
        except ValueError as error:
            raise HttpApiError("monday.com GraphQL returned non-JSON output") from error
        if not isinstance(document, dict):
            raise HttpApiError("monday.com GraphQL returned a non-object payload")
        try:
            _raise_for_graphql_errors(document)
        except TransientHttpApiError as error:
            await _maybe_sleep_retry_after(error.retry_after_seconds)
            raise
        return document


def _raise_for_graphql_errors(document: dict[str, Any]) -> None:
    errors = document.get("errors")
    if not errors:
        return
    if not isinstance(errors, list):
        raise HttpApiError("monday.com GraphQL errors payload is invalid")
    messages: list[str] = []
    for item in errors:
        if isinstance(item, dict):
            messages.append(str(item.get("message", item)))
        else:
            messages.append(str(item))
    message = "; ".join(messages) if messages else "unknown GraphQL error"
    if _is_permanent_complexity_error(message):
        raise HttpApiError(
            f"monday.com GraphQL error: {message}. Reduce settings.polling.batch_size "
            "so each query stays within the 5M complexity limit."
        )
    if _is_transient_graphql_error(message):
        raise TransientHttpApiError(
            f"monday.com GraphQL temporary error: {message}",
            retry_after_seconds=_retry_in_seconds_from_errors(errors),
        )
    raise HttpApiError(f"monday.com GraphQL error: {message}")


def _page_from_response(
    document: dict[str, Any],
    *,
    has_cursor: bool,
    board_id: str,
) -> dict[str, Any]:
    data = document.get("data")
    if data is None:
        raise HttpApiError("monday.com GraphQL response missing data")
    if not isinstance(data, dict):
        raise HttpApiError("monday.com GraphQL response data must be an object")
    if has_cursor:
        page = data.get("next_items_page")
        if not isinstance(page, dict):
            raise HttpApiError("monday.com GraphQL response missing next_items_page")
        return _normalize_page(page)
    boards = data.get("boards")
    if not isinstance(boards, list):
        raise HttpApiError("monday.com GraphQL response missing boards")
    if not boards:
        raise HttpApiError(
            f"monday.com board {board_id} not found or not accessible with this token; "
            "check board_id"
        )
    board = boards[0]
    if not isinstance(board, dict):
        raise HttpApiError("monday.com GraphQL board payload is unexpected")
    page = board.get("items_page")
    if not isinstance(page, dict):
        raise HttpApiError("monday.com GraphQL response missing items_page")
    return _normalize_page(page)


def _normalize_page(page: dict[str, Any]) -> dict[str, Any]:
    items = page.get("items")
    if not isinstance(items, list):
        raise HttpApiError("monday.com GraphQL items must be a list")
    return {"items": items, "cursor": page.get("cursor")}


def _is_permanent_complexity_error(message: str) -> bool:
    """Return whether the error is a single-query 5M complexity exceed (not retryable)."""
    lowered = message.lower()
    if "budget" in lowered:
        return False
    return "query complexity exceeds" in lowered or (
        "complexity" in lowered and "exceed" in lowered
    )


def _is_transient_graphql_error(message: str) -> bool:
    lowered = message.lower()
    if _is_permanent_complexity_error(message):
        return False
    return any(
        marker in lowered
        for marker in (
            "rate limit",
            "minute limit",
            "concurrency",
            "budget",
            "timeout",
            "timed out",
            "temporarily",
            "daily_limit",
            "daily limit",
        )
    )


def _retry_after_from_response(response: httpx.Response) -> float | None:
    header = response.headers.get("Retry-After")
    if header is None:
        return None
    try:
        return float(header.strip())
    except ValueError:
        return None


def _retry_in_seconds_from_errors(errors: list[object]) -> float | None:
    for item in errors:
        if not isinstance(item, dict):
            continue
        extensions = item.get("extensions")
        if not isinstance(extensions, dict):
            continue
        raw = extensions.get("retry_in_seconds")
        if isinstance(raw, (int, float)) and not isinstance(raw, bool):
            return float(raw)
        if isinstance(raw, str):
            try:
                return float(raw.strip())
            except ValueError:
                continue
    return None


async def _maybe_sleep_retry_after(seconds: float | None) -> None:
    if seconds is None or seconds <= 0:
        return
    await asyncio.sleep(min(seconds, _MAX_RETRY_AFTER_SECONDS))
