"""Offline tests for the github-project-items trigger: column filtering, paging, and mapping.

No test contacts GitHub or runs the real gh CLI.
"""

from __future__ import annotations

from typing import Any

import pytest
from curupira_plugins import __main__ as plugins_main
from curupira_plugins.github import triggers
from curupira_plugins.github.client import parse_nodes
from curupira_plugins.github.filters import ProjectFilters
from curupira_plugins.github.models import (
    ProjectItem,
    ProjectItemNode,
    ProjectV2,
    SearchConnection,
)
from curupira_sdk import RpcError


def _content(number: int, kind: str = "Issue", **overrides: Any) -> dict[str, Any]:
    content: dict[str, Any] = {
        "__typename": kind,
        "id": f"{kind}_{number}",
        "number": number,
        "title": f"Task {number}",
        "body": "Do it",
        "url": f"https://github.com/acme/api/issues/{number}",
        "state": "OPEN",
        "createdAt": "2026-10-01T00:00:00Z",
        "updatedAt": "2026-10-02T00:00:00Z",
        "author": {"login": "mario"},
        "labels": {"nodes": [{"name": "agent-ready"}]},
        "assignees": {"nodes": []},
        "milestone": None,
        "comments": {"totalCount": 1, "nodes": [{"author": {"login": "bob"}, "body": "hi"}]},
        "repository": {"nameWithOwner": "acme/api"},
    }
    if kind == "PullRequest":
        content |= {
            "headRefName": "feat",
            "baseRefName": "main",
            "headRefOid": "b" * 40,
            "isDraft": False,
            "mergeable": "MERGEABLE",
            "mergeStateStatus": "CLEAN",
            "reviewDecision": "APPROVED",
            "commits": {"nodes": [{"commit": {"statusCheckRollup": {"state": "SUCCESS"}}}]},
        }
    content.update(overrides)
    return content


def _item(number: int, column: str = "Ready", content: Any = "default") -> dict[str, Any]:
    return {
        "id": f"PVTI_{number}",
        "isArchived": False,
        "fieldValues": {
            "nodes": [
                {},  # repository/PR-link values arrive as empty objects
                {"text": f"Task {number}", "field": {"name": "Title"}},
                {"name": column, "field": {"name": "Status"}},
                {"name": "P1", "field": {"name": "Priority"}},
            ]
        },
        "content": _content(number) if content == "default" else content,
    }


def _page(nodes: list[dict[str, Any]], *, cursor: str | None = None) -> SearchConnection:
    return SearchConnection.model_validate(
        {"pageInfo": {"hasNextPage": cursor is not None, "endCursor": cursor}, "nodes": nodes}
    )


def _filters(**overrides: Any) -> ProjectFilters:
    return ProjectFilters(**({"owner": "acme", "project": 5, "column": ["Ready"]} | overrides))


def _map(filters: ProjectFilters, raw: dict[str, Any]) -> ProjectItem | None:
    node = ProjectItemNode.model_validate(raw)
    return triggers._project_item(filters, "Board", "https://github.com/orgs/acme/projects/5", node)


def test_item_in_column_maps_prompt_fields() -> None:
    item = _map(_filters(), _item(7))

    assert item is not None
    assert item.id == "acme/api#7"
    assert item.repo == "acme/api"
    assert item.item_type == "issue"
    assert item.project_column == "Ready"
    assert item.project_title == "Board"
    assert '"Priority": "P1"' in item.project_fields
    assert item.item_labels == ["agent-ready"]


def test_pull_request_content_exposes_branch_and_review_fields() -> None:
    raw = _item(9, content=_content(9, "PullRequest"))

    item = _map(_filters(), raw)

    assert item is not None
    assert item.item_type == "pull_request"
    assert item.pull_request_head_ref == "feat"


def test_column_match_is_case_insensitive_and_accepts_a_list() -> None:
    assert _map(_filters(column=["ready"]), _item(1)) is not None
    assert _map(_filters(column="READY"), _item(1)) is not None
    assert _map(_filters(column=["Todo", "Ready"]), _item(1)) is not None
    assert _map(_filters(column=["Done"]), _item(1)) is None


def test_other_status_field_name() -> None:
    raw = _item(1)
    raw["fieldValues"]["nodes"].append({"name": "Doing", "field": {"name": "Stage"}})

    assert _map(_filters(status_field="Stage", column="doing"), raw) is not None
    assert _map(_filters(status_field="Stage", column="Ready"), raw) is None


@pytest.mark.parametrize(
    "content",
    [None, {"__typename": "DraftIssue", "id": "D_1", "title": "idea"}],
)
def test_draft_and_redacted_items_are_skipped(content: Any) -> None:
    assert _map(_filters(), _item(1, content=content)) is None


def test_archived_items_are_skipped() -> None:
    raw = _item(1)
    raw["isArchived"] = True

    assert _map(_filters(), raw) is None


def test_content_filters() -> None:
    issue = _item(1)
    pull_request = _item(2, content=_content(2, "PullRequest"))

    assert _map(_filters(content="pull_request"), issue) is None
    assert _map(_filters(content="issue"), pull_request) is None
    assert _map(_filters(repo="acme/other"), issue) is None
    assert _map(_filters(repo="ACME/API"), issue) is not None
    assert _map(_filters(labels=["agent-ready"]), issue) is not None
    assert _map(_filters(labels=["missing"]), issue) is None
    assert _map(_filters(exclude_labels=["agent-ready"]), issue) is None
    assert _map(_filters(assignee="none"), issue) is not None
    assert _map(_filters(assignee="any"), issue) is None
    assert _map(_filters(author="mario"), issue) is not None
    assert _map(_filters(author="someone"), issue) is None


def test_closed_items_need_state_all() -> None:
    closed = _item(1, content=_content(1, state="CLOSED"))

    assert _map(_filters(), closed) is None
    assert _map(_filters(state="all"), closed) is not None
    assert _map(_filters(state="closed"), closed) is not None


def test_view_filter_quotes_values_and_skips_spaced_field_names() -> None:
    assert _filters(column=["Ready", "In Progress"]).view_filter() == 'status:Ready,"In Progress"'
    assert _filters(status_field="Sprint Stage").view_filter() is None


def test_discovery_pages_project_items_and_dedups(monkeypatch: pytest.MonkeyPatch) -> None:
    pages = {None: _page([_item(1), _item(2)], cursor="c1"), "c1": _page([_item(2), _item(3)])}
    calls: list[tuple[str | None, str | None]] = []

    class FakeClient:
        def project_items(
            self, owner: str, number: int, *, view_filter: str | None, after: str | None
        ) -> tuple[ProjectV2, SearchConnection]:
            calls.append((view_filter, after))
            project = ProjectV2.model_validate(
                {
                    "title": "Board",
                    "url": "u",
                    "items": {"pageInfo": {"hasNextPage": False}, "nodes": []},
                }
            )
            return project, pages[after]

    monkeypatch.setattr(triggers, "_CLIENT", FakeClient())
    monkeypatch.setattr(triggers, "_FEEDS", {})

    numbers = []
    while item := triggers.github_project_items(owner="acme", project=5, column="Ready"):
        numbers.append(item.item_number)

    assert numbers == [1, 2, 3]
    assert calls == [("status:Ready", None), ("status:Ready", "c1")]


def test_parse_nodes_tolerates_untyped_field_values() -> None:
    nodes = parse_nodes(_page([_item(1)]), ProjectItemNode)

    assert nodes[0].field_values.by_name() == {
        "Title": "Task 1",
        "Status": "Ready",
        "Priority": "P1",
    }


@pytest.mark.parametrize(
    "bad",
    [
        {"owner": "acme", "project": 0, "column": "Ready"},
        {"owner": "acme", "project": 5, "column": []},
        {"owner": "acme", "project": 5, "column": " "},
        {"owner": "acme", "project": 5, "column": "Ready", "content": "epic"},
        {"owner": "acme", "project": 5, "column": "Ready", "repo": "acme"},
    ],
)
def test_invalid_parameters_are_rejected(bad: dict[str, Any]) -> None:
    with pytest.raises(RpcError) as error:
        triggers._check_project_filters(bad)
    assert error.value.code == -32003


def test_validate_rpc_requires_column() -> None:
    result = plugins_main.app._handle_validate(
        {"trigger_type": "github-project-items", "configuration": {"owner": "acme", "project": 5}}
    )

    assert result["ok"] is False
    assert "column" in result["error"]


def test_project_trigger_prompt_fields_are_declared() -> None:
    spec = next(s for s in plugins_main.app.triggers() if s.name == "github-project-items")

    assert {"item_title", "project_column", "project_fields"} <= set(spec.prompt_fields)


def test_trigger_accepts_single_strings_where_lists_are_expected() -> None:
    result = plugins_main.app._handle_validate(
        {
            "trigger_type": "github-project-items",
            "configuration": {
                "owner": "acme",
                "project": 5,
                "column": "Ready",
                "labels": "backend",
                "exclude_labels": "blocked",
            },
        }
    )

    assert result["ok"] is True, result
