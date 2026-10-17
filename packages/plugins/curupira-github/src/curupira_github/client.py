"""GitHub access through the authenticated gh CLI: bearer token, GraphQL search, and paging."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.request
from collections import deque
from collections.abc import Callable
from typing import Any, Generic, TypeVar

from curupira_sdk import RpcError
from pydantic import ValidationError

from curupira_github.models import IssueNode, SearchConnection, SearchResponse

GRAPHQL_URL = "https://api.github.com/graphql"
TOKEN_CACHE_SECONDS = 300.0
PAGE_SIZE = 100
_RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
_ATTEMPTS = 3
_GH_TIMEOUT_SECONDS = 30
_HTTP_TIMEOUT_SECONDS = 30

SEARCH_QUERY = """
query CuripiraSearch($query: String!, $first: Int!, $after: String) {
  search(query: $query, type: ISSUE, first: $first, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on Issue {
        id number title body url state
        author { login }
        labels(first: 100) { nodes { name } }
      }
      ... on PullRequest {
        id number title body url state
        author { login }
        labels(first: 100) { nodes { name } }
        headRefName baseRefName headRefOid isDraft mergeable mergeStateStatus
      }
    }
  }
}
"""

NodeT = TypeVar("NodeT", bound=IssueNode)
ItemT = TypeVar("ItemT")


class GitHubCliToken:
    """Read the bearer token from `gh auth token`, caching it for five minutes."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self._clock = clock
        self._run = run
        self._token: str | None = None
        self._expires_at = 0.0

    def token(self) -> str:
        now = self._clock()
        if self._token is not None and now < self._expires_at:
            return self._token
        try:
            completed = self._run(
                ["gh", "auth", "token"],
                capture_output=True,
                text=True,
                timeout=_GH_TIMEOUT_SECONDS,
                check=False,
            )
        except FileNotFoundError as exc:
            raise RpcError(-32002, "Required executable not found: gh") from exc
        except subprocess.TimeoutExpired as exc:
            raise RpcError(-32002, "gh auth token timed out") from exc
        if completed.returncode != 0:
            detail = completed.stderr.strip() or f"exit status {completed.returncode}"
            raise RpcError(-32002, f"gh auth token failed: {detail}")
        token = completed.stdout.strip()
        if not token:
            raise RpcError(-32002, "gh auth token returned an empty token")
        self._token = token
        self._expires_at = now + TOKEN_CACHE_SECONDS
        return token


class GitHubClient:
    """Run GraphQL search requests with the gh CLI token and bounded retries."""

    def __init__(
        self,
        tokens: GitHubCliToken,
        *,
        endpoint: str = GRAPHQL_URL,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._tokens = tokens
        self._endpoint = endpoint
        self._sleep = sleep

    def search(self, query: str, *, after: str | None) -> SearchConnection:
        """Return one page of issue/pull-request search results for `query`."""
        payload = {
            "query": SEARCH_QUERY,
            "variables": {"query": query, "first": PAGE_SIZE, "after": after},
        }
        body = self._post(payload)
        try:
            response = SearchResponse.model_validate_json(body)
        except ValidationError as exc:
            raise RpcError(-32002, f"unexpected GitHub GraphQL response: {exc}") from exc
        if response.errors:
            messages = "; ".join(error.message for error in response.errors)
            raise RpcError(-32002, f"GitHub GraphQL error: {messages}")
        if response.data is None:
            raise RpcError(-32002, "GitHub GraphQL response has no data")
        return response.data.search

    def _post(self, payload: dict[str, Any]) -> bytes:
        data = json.dumps(payload).encode("utf-8")
        for attempt in range(1, _ATTEMPTS + 1):
            request = urllib.request.Request(
                self._endpoint,
                data=data,
                method="POST",
                headers={
                    "Authorization": f"Bearer {self._tokens.token()}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "curupira-github",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:
                    return bytes(response.read())
            except urllib.error.HTTPError as exc:
                # Close the response so the connection is released before retrying or raising.
                status = exc.code
                exc.close()
                if status not in _RETRY_STATUSES or attempt == _ATTEMPTS:
                    raise RpcError(
                        -32002, f"GitHub GraphQL request failed with status {status}"
                    ) from exc
            except urllib.error.URLError as exc:
                if attempt == _ATTEMPTS:
                    raise RpcError(-32002, f"GitHub GraphQL request failed: {exc.reason}") from exc
            self._sleep(2.0 ** (attempt - 1))
        raise RpcError(-32002, "GitHub GraphQL request failed")


def parse_nodes(connection: SearchConnection, model: type[NodeT]) -> list[NodeT]:
    """Validate raw search nodes into `model` (IssueNode or PullRequestNode)."""
    try:
        return [model.model_validate(node) for node in connection.nodes]
    except ValidationError as exc:
        raise RpcError(-32002, f"unexpected GitHub search node: {exc}") from exc


class Discovery(Generic[NodeT, ItemT]):
    """Yield each matching item once per process, fetching result pages lazily.

    The host starts a new extension process for every poll cycle, so the seen set only has
    to hold for one cycle. Items already completed are filtered by the host.
    """

    def __init__(
        self,
        *,
        fetch_page: Callable[[str | None], SearchConnection],
        parse_page: Callable[[SearchConnection], list[NodeT]],
        keep: Callable[[NodeT], bool],
        to_item: Callable[[NodeT], ItemT],
    ) -> None:
        self._fetch_page = fetch_page
        self._parse_page = parse_page
        self._keep = keep
        self._to_item = to_item
        self._pending: deque[NodeT] = deque()
        self._cursor: str | None = None
        self._has_more = True
        self._seen: set[str] = set()

    def next_item(self) -> ItemT | None:
        while True:
            while self._pending:
                node = self._pending.popleft()
                if node.id in self._seen:
                    continue
                self._seen.add(node.id)
                if self._keep(node):
                    return self._to_item(node)
            if not self._has_more:
                return None
            connection = self._fetch_page(self._cursor)
            self._pending.extend(self._parse_page(connection))
            self._has_more = connection.page_info.has_next_page
            self._cursor = connection.page_info.end_cursor
