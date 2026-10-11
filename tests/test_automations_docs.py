"""Automations reference page stays aligned with registered triggers and validates."""

from __future__ import annotations

import re
from pathlib import Path

from curupira.config import load_settings
from curupira.tasks import registry as trigger_registry

AUTOMATIONS_PAGE = Path("docs/en/automations.md")
_TOML_FENCE = re.compile(r"```toml\n(.*?)```", re.DOTALL)


def _toml_snippets(page: str) -> list[str]:
    """Return every fenced TOML block on the automations reference page."""
    return [match.group(1).strip() for match in _TOML_FENCE.finditer(page)]


async def test_automations_page_toml_snippets_validate(tmp_path: Path) -> None:
    """Every ```toml block on docs/en/automations.md must pass configuration load."""
    page = AUTOMATIONS_PAGE.read_text(encoding="utf-8")
    snippets = _toml_snippets(page)
    assert snippets, "expected at least one ```toml fence on the automations page"

    discovered_triggers: set[str] = set()
    for index, snippet in enumerate(snippets):
        path = tmp_path / f"automations-snippet-{index}.toml"
        path.write_text(snippet + "\n", encoding="utf-8")
        settings = await load_settings(path)
        assert settings.automations, f"snippet {index} defines no automations"
        for automation in settings.automations.values():
            discovered_triggers.add(automation.trigger_type)

    registered = set(trigger_registry.registered())
    assert discovered_triggers == registered, (
        "automations.md TOML snippets must cover every registered trigger type; "
        f"missing={sorted(registered - discovered_triggers)} "
        f"extra={sorted(discovered_triggers - registered)}"
    )


def test_automations_page_mentions_every_registered_trigger() -> None:
    """Fail if a registered trigger type is absent from the automations page body.

    Overview rows come from the ``triggers_table`` macro at build time, so the
    source must still name each type in a minimal TOML example
    (``trigger_type = "…"``).
    """
    page = AUTOMATIONS_PAGE.read_text(encoding="utf-8")
    missing = [
        trigger_type
        for trigger_type in trigger_registry.registered()
        if f'trigger_type = "{trigger_type}"' not in page
    ]
    assert not missing, f"registered triggers missing from automations.md: {missing}"
