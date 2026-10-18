"""Offline tests for the github trigger: query compilation, paging, auth caching, and models.

No test contacts GitHub or runs the real gh CLI.
"""

from __future__ import annotations

import io
import json
import subprocess
import urllib.error
from typing import Any

import pytest
from curupira_plugins import __main__ as plugins_main
from curupira_plugins.github import client as client_module
from curupira_plugins.github.triggers import (
    _check_pull_request_filters,
    _pull_request_feed,
    _pull_request_item,
)

app = plugins_main.app
from curupira_plugins.github.client import (
    Discovery,
    GitHubClient,
    GitHubCliToken,
    parse_nodes,
)
from curupira_plugins.github.filters import IssueFilters, PullRequestFilters
from curupira_plugins.github.models import (
    IssueItem,
    ProjectItem,
    PullRequestItem,
    PullRequestNode,
    SearchConnection,
    SearchResponse,
)
from curupira_sdk import RpcError


def _pr_node(number: int, **overrides: Any) -> dict[str, Any]:
    node: dict[str, Any] = {
        "id": f"PR_{number}",
        "number": number,
        "title": f"Bump thing {number}",
        "body": None,
        "url": f"https://github.com/acme/api/pull/{number}",
        "state": "OPEN",
        "author": {"login": "app/dependabot"},
        "labels": {"nodes": [{"name": "dependencies"}]},
        "headRefName": f"dependabot/uv/thing-{number}",
        "baseRefName": "main",
        "headRefOid": "a" * 40,
        "isDraft": False,
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "CLEAN",
    }
    node.update(overrides)
    return node


def _connection(
    nodes: list[dict[str, Any]], *, has_next: bool, cursor: str | None
) -> SearchConnection:
    payload = {
        "data": {
            "search": {
                "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
                "nodes": nodes,
            }
        }
    }
    response = SearchResponse.model_validate(payload)
    assert response.data is not None
    return response.data.search


def test_pull_request_query_compiles_documented_qualifiers() -> None:
    filters = PullRequestFilters(
        repo="caipora-labs/curupira",
        author="app/dependabot",
        draft=False,
        labels=["needs review", "dependencies"],
        exclude_labels=["blocked"],
        ci_status="success",
        review="none",
        sort="updated-desc",
    )

    assert filters.search_query() == (
        'is:pr repo:caipora-labs/curupira is:open label:"needs review" label:dependencies '
        "-label:blocked author:app/dependabot draft:false review:none status:success "
        "sort:updated-desc"
    )


def test_issue_query_maps_assignee_and_linked_pull_request() -> None:
    filters = IssueFilters(repo="acme/api", state="all", assignee="none", linked_pull_request=False)

    assert (
        filters.search_query() == "is:issue repo:acme/api no:assignee -linked:pr sort:created-asc"
    )


def test_repo_traversal_and_unknown_enum_values_are_rejected() -> None:
    with pytest.raises(RpcError) as traversal:
        _check_pull_request_filters(_pr_defaults() | {"repo": "acme/.."})
    assert traversal.value.code == -32003

    with pytest.raises(RpcError) as bad_state:
        _check_pull_request_filters(_pr_defaults() | {"repo": "acme/api", "state": "merged"})
    assert "state" in str(bad_state.value)


def _pr_defaults() -> dict[str, Any]:
    return {
        "labels": None,
        "exclude_labels": None,
        "state": "open",
        "assignee": None,
        "author": None,
        "milestone": None,
        "project": None,
        "draft": None,
        "base": None,
        "head": None,
        "review": None,
        "ci_status": None,
        "linked_issue": None,
        "mergeable": None,
        "merge_state": None,
        "sort": None,
    }


def test_discovery_pages_lazily_and_yields_each_item_once() -> None:
    pages = {
        None: _connection([_pr_node(1), _pr_node(2)], has_next=True, cursor="c1"),
        "c1": _connection([_pr_node(2), _pr_node(3)], has_next=False, cursor=None),
    }
    requested: list[str | None] = []

    def fetch(after: str | None) -> SearchConnection:
        requested.append(after)
        return pages[after]

    feed: Discovery[PullRequestNode, PullRequestItem] = Discovery(
        fetch_page=fetch,
        parse_page=lambda connection: parse_nodes(connection, PullRequestNode),
        keep=lambda node: True,
        to_item=lambda node: _pull_request_item("acme/api", node),
    )

    numbers = []
    while (item := feed.next_item()) is not None:
        numbers.append(item.pull_request_number)

    assert numbers == [1, 2, 3]
    assert requested == [None, "c1"]


def test_post_filters_drop_conflicting_pull_requests() -> None:
    filters = PullRequestFilters(repo="acme/api", mergeable=True, merge_state=["CLEAN"])

    assert filters.keeps(mergeable_state="MERGEABLE", merge_state_status="CLEAN")
    assert not filters.keeps(mergeable_state="CONFLICTING", merge_state_status="DIRTY")
    assert not filters.keeps(mergeable_state="MERGEABLE", merge_state_status="BLOCKED")


def test_pull_request_item_maps_placeholder_fields() -> None:
    node = parse_nodes(
        _connection([_pr_node(7, body="Release notes")], has_next=False, cursor=None),
        PullRequestNode,
    )[0]

    item = _pull_request_item("acme/api", node).model_dump()

    assert item["id"] == "7"
    assert item["repo"] == "acme/api"
    assert item["pull_request_number"] == 7
    assert item["pull_request_body"] == "Release notes"
    assert item["pull_request_head_ref"] == "dependabot/uv/thing-7"
    assert item["pull_request_head_sha"] == "a" * 40
    assert item["pull_request_author"] == "app/dependabot"
    assert item["pull_request_labels"] == ["dependencies"]
    assert item["pull_request_is_draft"] is False


def test_gh_token_is_cached_for_five_minutes() -> None:
    calls: list[list[str]] = []
    now = [1000.0]

    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="gho_test\n", stderr="")

    tokens = GitHubCliToken(clock=lambda: now[0], run=run)

    assert tokens.token() == "gho_test"
    assert tokens.token() == "gho_test"
    assert calls == [["gh", "auth", "token"]]

    now[0] += 301
    tokens.token()
    assert len(calls) == 2


def test_missing_gh_cli_is_reported_as_rpc_error() -> None:
    def run(argv: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("gh")

    with pytest.raises(RpcError, match="Required executable not found: gh"):
        GitHubCliToken(run=run).token()


def test_graphql_request_retries_transient_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    body = json.dumps(
        {"data": {"search": {"pageInfo": {"hasNextPage": False}, "nodes": []}}}
    ).encode()
    attempts: list[int] = []
    sleeps: list[float] = []

    def fake_urlopen(request: Any, timeout: float) -> Any:
        attempts.append(1)
        if len(attempts) == 1:
            raise urllib.error.HTTPError(request.full_url, 503, "unavailable", {}, io.BytesIO())
        return io.BytesIO(body)

    monkeypatch.setattr(client_module.urllib.request, "urlopen", fake_urlopen)
    tokens = GitHubCliToken(run=lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "tok", ""))
    github = GitHubClient(tokens, sleep=sleeps.append)

    page = github.search("is:pr repo:acme/api sort:created-asc", after=None)

    assert page.nodes == []
    assert len(attempts) == 2
    assert sleeps == [1.0]


def test_graphql_errors_surface_as_rpc_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    body = json.dumps({"errors": [{"message": "API rate limit exceeded"}]}).encode()

    def fake_urlopen(request: Any, timeout: float) -> Any:
        return io.BytesIO(body)

    monkeypatch.setattr(client_module.urllib.request, "urlopen", fake_urlopen)
    tokens = GitHubCliToken(run=lambda argv, **kw: subprocess.CompletedProcess(argv, 0, "tok", ""))

    with pytest.raises(RpcError, match="API rate limit exceeded"):
        GitHubClient(tokens).search("is:pr", after=None)


def test_trigger_returns_next_item_and_reuses_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    connection = _connection([_pr_node(11), _pr_node(12)], has_next=False, cursor=None)
    fetched: list[str | None] = []

    def fake_search(query: str, *, after: str | None) -> SearchConnection:
        fetched.append(after)
        return connection

    monkeypatch.setattr(
        "curupira_plugins.github.triggers._CLIENT",
        type("Fake", (), {"search": staticmethod(fake_search)})(),
    )
    monkeypatch.setattr("curupira_plugins.github.triggers._FEEDS", {})

    from curupira_plugins.github.triggers import github_pull_requests

    first = github_pull_requests(repo="acme/api", author="app/dependabot")
    second = github_pull_requests(repo="acme/api", author="app/dependabot")
    third = github_pull_requests(repo="acme/api", author="app/dependabot")

    assert first is not None and first.pull_request_number == 11
    assert second is not None and second.pull_request_number == 12
    assert third is None
    assert fetched == [None]


def test_validate_rpc_rejects_unknown_parameters() -> None:
    result = app._handle_validate(
        {
            "trigger_type": "github-pull-requests",
            "configuration": {"repo": "acme/api", "unknown_key": True},
        }
    )

    assert result["ok"] is False
    assert "unknown_key" in result["error"]


def test_feed_cache_key_is_per_filter_set() -> None:
    first = _pull_request_feed(PullRequestFilters(repo="acme/api", author="app/dependabot"))
    again = _pull_request_feed(PullRequestFilters(repo="acme/api", author="app/dependabot"))
    other = _pull_request_feed(PullRequestFilters(repo="acme/api", author="someone"))

    assert first is again
    assert first is not other


def test_search_response_without_data_is_reported() -> None:
    response = SearchResponse.model_validate({})

    assert response.data is None
    assert response.errors == []


def test_pull_request_item_maps_diff_and_people_fields() -> None:
    node = parse_nodes(
        _connection(
            [
                _pr_node(
                    5,
                    changedFiles=3,
                    additions=10,
                    deletions=2,
                    assignees={"nodes": [{"login": "mario"}]},
                    milestone={"title": "v1"},
                    closingIssuesReferences={"nodes": [{"number": 1, "url": "https://x/1"}]},
                )
            ],
            has_next=False,
            cursor=None,
        ),
        PullRequestNode,
    )[0]

    item = _pull_request_item("acme/api", node).model_dump()

    assert (item["pull_request_changed_files"], item["pull_request_additions"]) == (3, 10)
    assert item["pull_request_assignees"] == ["mario"]
    assert item["pull_request_milestone"] == "v1"
    assert item["pull_request_closing_issues"] == ["https://x/1"]


def test_items_leave_out_values_that_change_on_their_own() -> None:
    """The host hashes every returned field into the task identity, so volatile ones are omitted."""
    volatile = ("comment", "updated_at", "ci_status", "review_decision", "linked_pull_requests")
    for model in (IssueItem, PullRequestItem, ProjectItem):
        leaked = [name for name in model.model_fields if any(word in name for word in volatile)]
        assert not leaked, (model.__name__, leaked)


def test_single_string_labels_and_merge_state_are_accepted() -> None:
    for trigger, extra in (
        ("github-issues", {}),
        ("github-pull-requests", {"merge_state": "CLEAN"}),
    ):
        result = app._handle_validate(
            {
                "trigger_type": trigger,
                "configuration": {
                    "repo": "acme/api",
                    "labels": "agent-ready",
                    "exclude_labels": "blocked",
                    **extra,
                },
            }
        )
        assert result["ok"] is True, result

    filters = PullRequestFilters(repo="acme/api", labels="a", merge_state="CLEAN")  # type: ignore[arg-type]
    assert filters.labels == ["a"]
    assert filters.merge_state == ["CLEAN"]
