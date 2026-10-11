"""MkDocs macros for rendering versioned documentation data."""

import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple, Protocol

from curupira.agents import registry as agent_registry
from curupira.tasks import registry as trigger_registry
from curupira.tasks.base import Trigger


class MacroEnvironment(Protocol):
    """Interface provided by the MkDocs macros plugin."""

    def macro(self, function: Callable[[], str]) -> Callable[[], str]:
        """Register a zero-argument string-producing macro."""


class _TriggerGuide(NamedTuple):
    """Doc link and prerequisites for one built-in trigger type."""

    guide: str
    prerequisites: str


# Built-in trigger docs metadata. Unknown (plugin) types fall back in triggers_table().
_TRIGGER_GUIDES: dict[str, _TriggerGuide] = {
    "github-issues": _TriggerGuide(
        "github.md",
        "`gh` authenticated (`gh auth login`)",
    ),
    "github-pull-requests": _TriggerGuide(
        "github.md",
        "`gh` authenticated (`gh auth login`)",
    ),
    "azure-cli-pull-requests": _TriggerGuide(
        "automations.md#azure-devops-pull-requests",
        "`az` + Azure DevOps extension (`az login`)",
    ),
    "trello-cli-cards": _TriggerGuide(
        "trello.md",
        "Scale-Flow `trello-cli` (`trello auth login`)",
    ),
    "monday-items": _TriggerGuide(
        "monday.md",
        "`MONDAY_API_TOKEN` (or `token_env`) set",
    ),
    "cron": _TriggerGuide(
        "automations.md#cron",
        "None (local schedule)",
    ),
}

_TRIGGER_ORDER: tuple[str, ...] = (
    "github-issues",
    "github-pull-requests",
    "azure-cli-pull-requests",
    "trello-cli-cards",
    "monday-items",
    "cron",
)


def _trigger_summary(trigger: Trigger) -> str:
    """Return the first line of the configuration model docstring for the table."""
    doc = (trigger.configuration_model.__doc__ or "").strip()
    first = doc.splitlines()[0] if doc else trigger.trigger_type
    return first.replace("``", "`")


def _ordered_triggers() -> list[tuple[str, Trigger]]:
    """Return registered triggers in newcomer-friendly order, then extras."""
    registered = trigger_registry.registered()
    ordered = [name for name in _TRIGGER_ORDER if name in registered]
    extras = sorted(name for name in registered if name not in _TRIGGER_ORDER)
    return [(name, registered[name]) for name in [*ordered, *extras]]


def define_env(env: MacroEnvironment) -> None:
    """Register macros used by the documentation pages."""
    requirements_path = Path(__file__).parent / "docs" / "data" / "requirements.toml"
    with requirements_path.open("rb") as requirements_file:
        requirements = tomllib.load(requirements_file)

    @env.macro
    def requirements_list() -> str:
        """Render the installation requirements from the TOML source and agent registry."""
        python = requirements["python"]
        lines = [
            f"- Python {python['range']} ({python['platforms']}).",
        ]
        lines.extend(
            f"- [{tool['name']}]({tool['url']}) — {tool['detail']}"
            for tool in requirements["required_tools"]
        )
        optional_tools = requirements.get("optional_tools", [])
        if optional_tools:
            lines.append("- Optional forge CLIs, only when their triggers are configured:")
            lines.extend(
                f"  - [{tool['name']}]({tool['url']}) — {tool['detail']}" for tool in optional_tools
            )
        lines.append("- Install only the CLIs used by configured profiles:")
        lines.extend(
            f"  - [{adapter.display_name} (`{adapter.executable}`)]({adapter.install_url})"
            for adapter in agent_registry.registered().values()
        )
        return "\n".join(lines)

    @env.macro
    def providers_table() -> str:
        """Render one row per registered coding-agent provider."""
        lines = [
            "| Provider | Executable | Install |",
            "| --- | --- | --- |",
        ]
        lines.extend(
            f"| [{adapter.display_name}](providers/{provider}.md) | `{adapter.executable}` "
            f"| <{adapter.install_url}> |"
            for provider, adapter in agent_registry.registered().items()
        )
        return "\n".join(lines)

    @env.macro
    def triggers_table() -> str:
        """Render one row per registered automation trigger."""
        lines = [
            "| Trigger type | What it does | Prerequisites | Guide |",
            "| --- | --- | --- | --- |",
        ]
        for trigger_type, trigger in _ordered_triggers():
            guide_meta = _TRIGGER_GUIDES.get(trigger_type)
            if guide_meta is None:
                guide = "plugins.md"
                prerequisites = "See the plugin documentation"
                link_label = "Plugins"
            else:
                guide = guide_meta.guide
                prerequisites = guide_meta.prerequisites
                link_label = "Guide"
            summary = _trigger_summary(trigger)
            lines.append(
                f"| `{trigger_type}` | {summary} | {prerequisites} | [{link_label}]({guide}) |"
            )
        return "\n".join(lines)
