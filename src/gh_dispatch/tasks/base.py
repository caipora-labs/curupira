"""Abstract contracts for task feeds and task sources."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from gh_dispatch.models import ResolvedAutomation, Task


class TaskFeed(ABC):
    """Discovery interface shared by one-shot dispatch and continuous polling."""

    @abstractmethod
    async def poll(self, *, preview: bool = False) -> list[Task]:
        """Return available tasks; preview must not persist state."""

    @abstractmethod
    def stream(self) -> AsyncIterator[Task]:
        """Yield tasks continuously with source-appropriate waits."""


class TaskSource(ABC):
    """Discover tasks for a resolved automation."""

    @abstractmethod
    async def discover(self, automation: ResolvedAutomation, limit: int) -> list[Task]:
        """Return up to ``limit`` tasks matching the automation."""
