"""Tests for Pydantic-to-template flattening."""

from curupira.models.base import ValidatedModel
from curupira.models.items import IssueItem
from curupira.models.templates import common_prompt_context, flatten_for_template


class Nested(ValidatedModel):
    label: str


class SampleItem(ValidatedModel):
    name: str
    count: int
    enabled: bool
    missing: str | None = None
    tags: list[str]
    nested: Nested
    mapping: dict[str, int]


def test_flatten_for_template_stringifies_scalars_and_json_structures() -> None:
    assert flatten_for_template(
        SampleItem(
            name="ops",
            count=3,
            enabled=True,
            missing=None,
            tags=["a", "b"],
            nested=Nested(label="x"),
            mapping={"n": 1},
        )
    ) == {
        "name": "ops",
        "count": "3",
        "enabled": "true",
        "missing": "",
        "tags": '["a","b"]',
        "nested": '{"label":"x"}',
        "mapping": '{"n":1}',
    }


def test_common_prompt_context_derives_task_body_from_item() -> None:
    item = IssueItem(
        issue_number="7",
        issue_title="Fix",
        issue_body="Details",
        issue_url="https://example.test/7",
    )

    context = common_prompt_context(
        repo="acme/api",
        automation_id="issues",
        task_type="issue",
        task_number="7",
        task_title="Fix",
        task_url="https://example.test/7",
        item=item,
    )

    assert context["task_body"] == "Details"
    assert context["issue_number"] == "7"
    assert context["repo"] == "acme/api"
