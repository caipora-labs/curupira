"""Async GitHub GraphQL client for issue and pull-request discovery."""

from __future__ import annotations

from typing import Any, cast

import httpx
from pydantic import TypeAdapter, ValidationError
from pyresilience import RetryConfig, resilient

from curupira.clients.github_auth import GitHubCliTokenProvider
from curupira.clients.github_search import matches_pull_request_post_filters
from curupira.clients.process import AsyncProcessRunner
from curupira.errors import HttpApiError, TransientHttpApiError
from curupira.models.configuration import (
    IssueAutomationConfiguration,
    PullRequestAutomationConfiguration,
)
from curupira.models.github import GhIssue, GhPullRequest, GitHubSearchRequest

_GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
_SEARCH_QUERY = """
query CurupiraSearch($searchQuery: String!, $first: Int!) {
  search(query: $searchQuery, type: ISSUE, first: $first) {
    nodes {
      __typename
      ... on Issue {
        number
        title
        body
        url
        state
        labels(first: 20) {
          nodes {
            name
          }
        }
      }
      ... on PullRequest {
        number
        title
        body
        url
        state
        isDraft
        headRefName
        baseRefName
        mergeable
        mergeStateStatus
        labels(first: 20) {
          nodes {
            name
          }
        }
      }
    }
  }
}
"""


def _raise_for_graphql_errors(document: dict[str, Any]) -> None:
    errors = document.get("errors")
    if not errors:
        return
    message = "; ".join(str(item.get("message", item)) for item in errors if isinstance(item, dict))
    if _is_transient_graphql_error(message):
        raise TransientHttpApiError(f"GitHub GraphQL temporary error: {message}")
    raise HttpApiError(f"GitHub GraphQL error: {message}")


def _nodes_from_response(document: dict[str, Any], expected_typename: str) -> list[dict[str, Any]]:
    data = document.get("data")
    if not isinstance(data, dict):
        raise HttpApiError("GitHub GraphQL response missing data")
    search = data.get("search")
    if not isinstance(search, dict):
        raise HttpApiError("GitHub GraphQL response missing search results")
    nodes = search.get("nodes")
    if not isinstance(nodes, list):
        raise HttpApiError("GitHub GraphQL search nodes must be a list")
    items: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict) or node.get("__typename") != expected_typename:
            continue
        labels = node.get("labels")
        label_nodes: list[dict[str, str]] = []
        if isinstance(labels, dict):
            raw_nodes = labels.get("nodes")
            if isinstance(raw_nodes, list):
                label_nodes = [
                    {"name": str(label["name"])}
                    for label in raw_nodes
                    if isinstance(label, dict) and "name" in label
                ]
        item = {key: value for key, value in node.items() if key != "__typename"}
        item["labels"] = label_nodes
        items.append(item)
    return items


class GitHubGraphQLClient:
    """List GitHub issues and pull requests through GraphQL Search."""

    def __init__(
        self,
        runner: AsyncProcessRunner | None = None,
        *,
        token_provider: GitHubCliTokenProvider | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        endpoint: str = _GITHUB_GRAPHQL_URL,
    ) -> None:
        self._token_provider = token_provider or GitHubCliTokenProvider(runner)
        self._transport = transport
        self._endpoint = endpoint

    async def list_issues(
        self,
        request: GitHubSearchRequest,
        *,
        configuration: IssueAutomationConfiguration | None = None,
    ) -> list[GhIssue]:
        """Search issues and validate the GraphQL payload."""
        del configuration
        payload = await self._search_resilient(request)
        try:
            return TypeAdapter(list[GhIssue]).validate_python(payload)
        except ValidationError as error:
            raise HttpApiError(f"GitHub returned invalid issue JSON: {error}") from error

    async def list_pull_requests(
        self,
        request: GitHubSearchRequest,
        *,
        configuration: PullRequestAutomationConfiguration | None = None,
    ) -> list[GhPullRequest]:
        """Search pull requests, apply merge post-filters, and validate the payload."""
        payload = await self._search_resilient(request)
        if configuration is not None:
            payload = [
                item
                for item in payload
                if matches_pull_request_post_filters(
                    mergeable=cast(str | None, item.get("mergeable")),
                    merge_state_status=cast(str | None, item.get("mergeStateStatus")),
                    configuration=configuration,
                )
            ]
        try:
            return TypeAdapter(list[GhPullRequest]).validate_python(payload)
        except ValidationError as error:
            raise HttpApiError(f"GitHub returned invalid pull request JSON: {error}") from error

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
    async def _search_resilient(self, request: GitHubSearchRequest) -> list[dict[str, Any]]:
        token = await self._token_provider.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-Github-Next-Global-ID": "1",
        }
        body = {
            "query": _SEARCH_QUERY,
            "variables": {"searchQuery": request.query, "first": request.limit},
        }
        async with httpx.AsyncClient(transport=self._transport, timeout=30.0) as client:
            try:
                response = await client.post(self._endpoint, headers=headers, json=body)
            except httpx.TransportError as error:
                raise TransientHttpApiError(f"GitHub GraphQL transport failed: {error}") from error
        if response.status_code in {429, 502, 503, 504} or response.status_code >= 500:
            raise TransientHttpApiError(
                f"GitHub GraphQL temporarily failed with status {response.status_code}"
            )
        if response.status_code >= 400:
            raise HttpApiError(
                f"GitHub GraphQL failed with status {response.status_code}: {response.text}"
            )
        try:
            document = response.json()
        except ValueError as error:
            raise HttpApiError("GitHub GraphQL returned non-JSON output") from error
        if not isinstance(document, dict):
            raise HttpApiError("GitHub GraphQL returned a non-object payload")
        _raise_for_graphql_errors(document)
        expected = "Issue" if request.item_kind == "issue" else "PullRequest"
        return _nodes_from_response(document, expected)


def _is_transient_graphql_error(message: str) -> bool:
    lowered = message.lower()
    return any(
        marker in lowered
        for marker in ("rate limit", "timeout", "timed out", "something went wrong")
    )
