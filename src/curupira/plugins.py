"""Stable public API for third-party trigger and coding-agent plugins and their discovery.

Plugins import only from this module. Trigger plugins advertise a ``Trigger`` subclass
(or instance) under the ``curupira.triggers`` entry-point group; agent plugins advertise
a ``CodingAgentCliAdapter`` subclass under the ``curupira.agents`` entry-point group.
"""

from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points

from curupira.agents.base import CodingAgentCliAdapter
from curupira.agents.interactive import (
    InteractiveLaunchSpec,
    default_pty_env,
    spec_available,
)
from curupira.clients.process import AsyncProcessRunner
from curupira.errors import DispatchError, PluginLoadError
from curupira.models import (
    CliProfileBase,
    CodingTaskRequest,
    CommandRequest,
    ProcessResult,
    ResolvedAutomation,
    Task,
    TaskIdentity,
    flatten_for_template,
)
from curupira.models.base import Identifier, NonEmptyString, ValidatedModel
from curupira.models.configuration import AutomationConfigurationBase
from curupira.tasks.base import (
    PLUGIN_API_VERSION,
    FeedDependencies,
    TaskFeed,
    TaskSource,
    Trigger,
    TriggerState,
)
from curupira.tasks.feed import PollingTaskFeed
from curupira.vcs.base import VersionControl

ENTRY_POINT_GROUP = "curupira.triggers"
AGENT_ENTRY_POINT_GROUP = "curupira.agents"

__all__ = [
    "AGENT_ENTRY_POINT_GROUP",
    "ENTRY_POINT_GROUP",
    "PLUGIN_API_VERSION",
    "AsyncProcessRunner",
    "AutomationConfigurationBase",
    "CliProfileBase",
    "CodingAgentCliAdapter",
    "CodingTaskRequest",
    "CommandRequest",
    "DispatchError",
    "FeedDependencies",
    "Identifier",
    "InteractiveLaunchSpec",
    "LoadedAgentPlugin",
    "LoadedPlugin",
    "NonEmptyString",
    "PollingTaskFeed",
    "ProcessResult",
    "ResolvedAutomation",
    "Task",
    "TaskFeed",
    "TaskIdentity",
    "TaskSource",
    "Trigger",
    "TriggerState",
    "ValidatedModel",
    "VersionControl",
    "default_pty_env",
    "flatten_for_template",
    "load_agent_plugins",
    "load_plugins",
    "loaded_agent_plugins",
    "loaded_plugins",
    "spec_available",
]


@dataclass(frozen=True)
class LoadedPlugin:
    """Provenance of a trigger registered from an installed distribution.

    Attributes:
        entry_point: Entry-point name declared by the distribution.
        distribution: Installed distribution name.
        version: Installed distribution version.
        trigger_type: Trigger type the plugin registered.
    """

    entry_point: str
    distribution: str
    version: str
    trigger_type: str


_loaded: list[LoadedPlugin] | None = None
_loading = False


def load_plugins() -> list[LoadedPlugin]:
    """Register every installed trigger plugin exactly once per process."""
    global _loaded, _loading
    if _loaded is not None:
        return _loaded
    # A plugin module may look up triggers while it is being imported.
    if _loading:
        return []
    _loading = True
    try:
        plugins = [_load(entry_point) for entry_point in entry_points(group=ENTRY_POINT_GROUP)]
    finally:
        _loading = False
    _loaded = plugins
    return plugins


def loaded_plugins() -> list[LoadedPlugin]:
    """Return plugins registered so far, loading them if needed."""
    return list(load_plugins())


def _load(entry_point: EntryPoint) -> LoadedPlugin:
    from curupira.tasks.registry import register

    distribution, version = _origin(entry_point)
    try:
        loaded: object = entry_point.load()
    except Exception as error:
        raise PluginLoadError(entry_point.name, distribution, repr(error)) from error
    trigger = _instantiate(loaded, entry_point.name, distribution)
    if trigger.api_version != PLUGIN_API_VERSION:
        raise PluginLoadError(
            entry_point.name,
            distribution,
            f"requires plugin API {trigger.api_version}, Curupira provides {PLUGIN_API_VERSION}",
        )
    try:
        register(trigger)
    except ValueError as error:
        raise PluginLoadError(entry_point.name, distribution, str(error)) from error
    return LoadedPlugin(entry_point.name, distribution, version, trigger.trigger_type)


def _instantiate(loaded: object, name: str, distribution: str) -> Trigger:
    if isinstance(loaded, Trigger):
        return loaded
    if isinstance(loaded, type) and issubclass(loaded, Trigger):
        try:
            return loaded()
        except Exception as error:
            raise PluginLoadError(name, distribution, repr(error)) from error
    raise PluginLoadError(name, distribution, "entry point is not a Trigger subclass or instance")


@dataclass(frozen=True)
class LoadedAgentPlugin:
    """Provenance of a coding-agent adapter registered from an installed distribution.

    Attributes:
        entry_point: Entry-point name declared by the distribution.
        distribution: Installed distribution name.
        version: Installed distribution version.
        provider: Coding-agent provider the plugin registered.
    """

    entry_point: str
    distribution: str
    version: str
    provider: str


_agents_loaded: list[LoadedAgentPlugin] | None = None
_agents_loading = False


def load_agent_plugins() -> list[LoadedAgentPlugin]:
    """Register every installed coding-agent plugin exactly once per process."""
    global _agents_loaded, _agents_loading
    if _agents_loaded is not None:
        return _agents_loaded
    # A plugin module may look up providers while it is being imported.
    if _agents_loading:
        return []
    _agents_loading = True
    try:
        plugins = [
            _load_agent(entry_point) for entry_point in entry_points(group=AGENT_ENTRY_POINT_GROUP)
        ]
    finally:
        _agents_loading = False
    _agents_loaded = plugins
    return plugins


def loaded_agent_plugins() -> list[LoadedAgentPlugin]:
    """Return agent plugins registered so far, loading them if needed."""
    return list(load_agent_plugins())


def _load_agent(entry_point: EntryPoint) -> LoadedAgentPlugin:
    from curupira.agents.registry import register

    distribution, version = _origin(entry_point)
    try:
        loaded: object = entry_point.load()
    except Exception as error:
        raise PluginLoadError(entry_point.name, distribution, repr(error)) from error
    if not isinstance(loaded, type) or not issubclass(loaded, CodingAgentCliAdapter):
        raise PluginLoadError(
            entry_point.name, distribution, "entry point is not a CodingAgentCliAdapter subclass"
        )
    if loaded.api_version != PLUGIN_API_VERSION:
        raise PluginLoadError(
            entry_point.name,
            distribution,
            f"requires plugin API {loaded.api_version}, Curupira provides {PLUGIN_API_VERSION}",
        )
    try:
        register(loaded)
    except ValueError as error:
        raise PluginLoadError(entry_point.name, distribution, str(error)) from error
    return LoadedAgentPlugin(entry_point.name, distribution, version, loaded.provider)


def _origin(entry_point: EntryPoint) -> tuple[str, str]:
    if entry_point.dist is None:
        return "unknown", "unknown"
    return entry_point.dist.name, entry_point.dist.version
