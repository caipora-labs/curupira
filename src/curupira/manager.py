"""Initialize Pluggy and register built-in coding-agent providers with the core registry.

The manager owns discovery of in-tree providers. It does not load third-party entry
points; ``curupira.plugins.load_agent_plugins`` keeps that responsibility so the public
plugin API stays unchanged.
"""

from __future__ import annotations

import importlib

import pluggy

from curupira import hooks
from curupira.agents.base import CodingAgentCliAdapter

_BUILT_IN_PROVIDER_MODULES: tuple[str, ...] = (
    "curupira.providers.claude.provider",
    "curupira.providers.codex.provider",
    "curupira.providers.copilot.provider",
    "curupira.providers.cursor.provider",
    "curupira.providers.gemini.provider",
    "curupira.providers.kilo.provider",
    "curupira.providers.opencode.provider",
    "curupira.providers.pi.provider",
    "curupira.providers.qwen.provider",
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


def load_built_in_adapters() -> None:
    """Register built-in providers with the coding-agent registry once per process."""
    global _loaded
    if _loaded:
        return

    from curupira.agents.registry import register

    manager = create_manager()
    register_built_in_providers(manager)
    for adapter in collect_built_in_adapters(manager):
        register(adapter)
    _loaded = True
