"""Compatibility re-export of the monday.com board item trigger."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from curupira.providers.monday.provider import MondayItemSource as MondayItemSource
    from curupira.providers.monday.provider import MondayItemTrigger as MondayItemTrigger


def __getattr__(name: str) -> object:
    """Load the monday.com provider lazily to avoid import cycles."""
    if name in {"MondayItemSource", "MondayItemTrigger"}:
        from curupira.providers.monday import provider as module

        return getattr(module, name)
    raise AttributeError(name)
