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
from curupira.models.github import GhIssue, GhPullRequest, GhTaskViewRequest, GitHubSearchRequest

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
        headRefOid
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
_ISSUE_VIEW_QUERY = """
query CurupiraIssueView($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    issue(number: $number) {
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
  }
}
"""
_PULL_REQUEST_VIEW_QUERY = """
query CurupiraPullRequestView($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      number
      title
      body
      url
      state
      isDraft
      headRefName
      baseRefName
      headRefOid
      mergeable
      mergeStateStatus
      reviewDecision
      mergedAt
      labels(first: 20) {
        nodes {
          name
        }
      }
      closingIssuesReferences(first: 20) {
        nodes {
          number
          repository {
            nameWithOwner
          }
        }
      }
      commits(last: 1) {
        nodes {
          commit {
            statusCheckRollup {
              contexts(first: 100) {
                nodes {
                  __typename
                  ... on CheckRun {
                    conclusion
                    status
                  }
                  ... on StatusContext {
                    state
                  }
                }
              }
            }
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


def _flatten_labels(node: dict[str, Any]) -> dict[str, Any]:
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
    return item


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
        items.append(_flatten_labels(node))
    return items


def _split_repo(repo: str) -> tuple[str, str]:
    owner, separator, name = repo.partition("/")
    if not separator or not owner or not name or "/" in name:
        raise HttpApiError(f"GitHub repository must be owner/name, got {repo!r}")
    return owner, name


def _normalize_closing_references(node: dict[str, Any]) -> list[dict[str, Any]]:
    references = node.get("closingIssuesReferences")
    if not isinstance(references, dict):
        return []
    raw_nodes = references.get("nodes")
    if not isinstance(raw_nodes, list):
        return []
    return [item for item in raw_nodes if isinstance(item, dict)]


def _normalize_status_checks(node: dict[str, Any]) -> list[dict[str, str | None]]:
    commits = node.get("commits")
    if not isinstance(commits, dict):
        return []
    commit_nodes = commits.get("nodes")
    if not isinstance(commit_nodes, list) or not commit_nodes:
        return []
    first = commit_nodes[0]
    if not isinstance(first, dict):
        return []
    commit = first.get("commit")
    if not isinstance(commit, dict):
        return []
    rollup = commit.get("statusCheckRollup")
    if not isinstance(rollup, dict):
        return []
    contexts = rollup.get("contexts")
    if not isinstance(contexts, dict):
        return []
    context_nodes = contexts.get("nodes")
    if not isinstance(context_nodes, list):
        return []
    checks: list[dict[str, str | None]] = []
    for item in context_nodes:
        if not isinstance(item, dict):
            continue
        conclusion = item.get("conclusion")
        state = item.get("state") or item.get("status")
        checks.append(
            {
                "conclusion": None if conclusion is None else str(conclusion),
                "state": None if state is None else str(state),
            }
        )
    return checks


def _normalize_pull_request_node(node: dict[str, Any]) -> dict[str, Any]:
    item = _flatten_labels(node)
    item["closingIssuesReferences"] = _normalize_closing_references(node)
    item["statusCheckRollup"] = _normalize_status_checks(node)
    item.pop("commits", None)
    return item


class GitHubGraphQLClient:
    """List and view GitHub issues and pull requests through GraphQL."""

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

    async def view_issue(self, request: GhTaskViewRequest) -> GhIssue:
        """Fetch one issue's current state rather than trusting a saved task snapshot."""
        owner, name = _split_repo(request.repo)
        document = await self._graphql_resilient(
            _ISSUE_VIEW_QUERY,
            {"owner": owner, "name": name, "number": request.number},
        )
        node = _repository_child(document, "issue")
        try:
            return GhIssue.model_validate(_flatten_labels(node))
        except ValidationError as error:
            raise HttpApiError(f"GitHub returned invalid issue JSON: {error}") from error

    async def view_pull_request(self, request: GhTaskViewRequest) -> GhPullRequest:
        """Fetch current pull-request stage, head, checks, and closing references."""
        owner, name = _split_repo(request.repo)
        document = await self._graphql_resilient(
            _PULL_REQUEST_VIEW_QUERY,
            {"owner": owner, "name": name, "number": request.number},
        )
        node = _repository_child(document, "pullRequest")
        try:
            return GhPullRequest.model_validate(_normalize_pull_request_node(node))
        except ValidationError as error:
            raise HttpApiError(f"GitHub returned invalid pull request JSON: {error}") from error

    async def list_pull_requests_for_issue(
        self, repo: str, issue_number: int
    ) -> list[GhPullRequest]:
        """Find open PRs whose body or closing metadata may reference an issue."""
        return await self.list_pull_requests(
            GitHubSearchRequest(
                repo=repo,
                query=f"repo:{repo} is:pr is:open {issue_number} in:body",
                limit=100,
                item_kind="pull_request",
            )
        )

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
        document = await self._graphql_resilient(
            _SEARCH_QUERY,
            {"searchQuery": request.query, "first": request.limit},
        )
        expected = "Issue" if request.item_kind == "issue" else "PullRequest"
        return _nodes_from_response(document, expected)

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
    async def _graphql_resilient(
        self, query: str, variables: dict[str, Any]
    ) -> dict[str, Any]:
        token = await self._token_provider.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-Github-Next-Global-ID": "1",
        }
        body = {"query": query, "variables": variables}
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
        return document


def _repository_child(document: dict[str, Any], field: str) -> dict[str, Any]:
    data = document.get("data")
    if not isinstance(data, dict):
        raise HttpApiError("GitHub GraphQL response missing data")
    repository = data.get("repository")
    if not isinstance(repository, dict):
        raise HttpApiError("GitHub GraphQL response missing repository")
    node = repository.get(field)
    if not isinstance(node, dict):
        raise HttpApiError(f"GitHub GraphQL response missing {field}")
    return node


def _is_transient_graphql_error(message: str) -> bool:
    lowered = message.lower()
    return any(
        marker in lowered
        for marker in ("rate limit", "timeout", "timed out", "something went wrong")
    )
