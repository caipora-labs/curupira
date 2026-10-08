"""Stable public API for third-party trigger plugins and their discovery.

Plugins import only from this module and advertise a ``Trigger`` subclass (or
instance) under the ``curupira.triggers`` entry-point group.
"""

from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points

from curupira.clients.process import AsyncProcessRunner
from curupira.errors import DispatchError, PluginLoadError
from curupira.models import CommandRequest, ProcessResult, ResolvedAutomation, Task, TaskIdentity
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

__all__ = [
    "ENTRY_POINT_GROUP",
    "PLUGIN_API_VERSION",
    "AsyncProcessRunner",
    "AutomationConfigurationBase",
    "CommandRequest",
    "DispatchError",
    "FeedDependencies",
    "Identifier",
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
    "load_plugins",
    "loaded_plugins",
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

    distribution = entry_point.dist.name if entry_point.dist is not None else "unknown"
    version = entry_point.dist.version if entry_point.dist is not None else "unknown"
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
