"""Initialize Pluggy and register built-in providers with the core registries.

The manager owns discovery of in-tree providers. Each provider module may contribute
coding-agent adapters, triggers, or both. It does not load third-party entry points;
``curupira.plugins`` keeps that responsibility so the public plugin API stays unchanged.
"""

from __future__ import annotations

import importlib

import pluggy

from curupira import hooks
from curupira.agents.base import CodingAgentCliAdapter
from curupira.tasks.base import Trigger

_BUILT_IN_PROVIDER_MODULES: tuple[str, ...] = (
    "curupira.providers.azure.provider",
    "curupira.providers.claude.provider",
    "curupira.providers.codex.provider",
    "curupira.providers.copilot.provider",
    "curupira.providers.cron.provider",
    "curupira.providers.cursor.provider",
    "curupira.providers.gemini.provider",
    "curupira.providers.github.provider",
    "curupira.providers.kilo.provider",
    "curupira.providers.monday.provider",
    "curupira.providers.opencode.provider",
    "curupira.providers.pi.provider",
    "curupira.providers.qwen.provider",
    "curupira.providers.trello.provider",
)

_loaded = False


def create_manager() -> pluggy.PluginManager:
    """Return a PluginManager with Curupira's provider hook specifications."""
    manager = pluggy.PluginManager(hooks.PROJECT_NAME)
    manager.add_hookspecs(hooks)
    return manager


def register_built_in_providers(manager: pluggy.PluginManager) -> None:
    """Register every official provider module on ``manager``."""
    for module_name in _BUILT_IN_PROVIDER_MODULES:
        module = importlib.import_module(module_name)
        if manager.is_registered(module):
            continue
        manager.register(module, name=module_name)


def collect_built_in_adapters(
    manager: pluggy.PluginManager | None = None,
) -> list[type[CodingAgentCliAdapter]]:
    """Collect adapter classes from built-in provider hook implementations."""
    plugin_manager = manager if manager is not None else create_manager()
    if manager is None:
        register_built_in_providers(plugin_manager)
    adapters: list[type[CodingAgentCliAdapter]] = []
    for contributed in plugin_manager.hook.curupira_coding_agent_adapters():
        adapters.extend(contributed)
    return adapters


def collect_built_in_triggers(
    manager: pluggy.PluginManager | None = None,
) -> list[Trigger]:
    """Collect trigger instances from built-in provider hook implementations."""
    plugin_manager = manager if manager is not None else create_manager()
    if manager is None:
        register_built_in_providers(plugin_manager)
    triggers: list[Trigger] = []
    for contributed in plugin_manager.hook.curupira_triggers():
        triggers.extend(contributed)
    return triggers


def load_built_in_providers() -> None:
    """Register built-in agents and triggers with their registries once per process."""
    global _loaded
    if _loaded:
        return

    from curupira.agents.registry import register as register_adapter
    from curupira.tasks.registry import register as register_trigger

    manager = create_manager()
    register_built_in_providers(manager)
    for adapter in collect_built_in_adapters(manager):
        register_adapter(adapter)
    for trigger in collect_built_in_triggers(manager):
        register_trigger(trigger)
    _loaded = True


def load_built_in_adapters() -> None:
    """Register built-in providers (agents and triggers); kept for call-site clarity."""
    load_built_in_providers()
