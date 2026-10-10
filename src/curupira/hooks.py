"""Pluggy hook specifications for built-in providers.

A provider package may contribute zero or more coding-agent adapters and zero or more
triggers through these hooks. Built-in providers and the core share this contract.
Third-party plugins continue to register through the ``curupira.agents`` /
``curupira.triggers`` entry-point groups and the public ``curupira.plugins`` API; they
do not need to depend on Pluggy.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import pluggy

if TYPE_CHECKING:
    from curupira.agents.base import CodingAgentCliAdapter
    from curupira.tasks.base import Trigger

PROJECT_NAME = "curupira"
hookspec = pluggy.HookspecMarker(PROJECT_NAME)
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


@hookspec
def curupira_coding_agent_adapters() -> Sequence[type[CodingAgentCliAdapter]]:
    """Return coding-agent adapter classes contributed by one provider plugin."""
    return ()


@hookspec
def curupira_triggers() -> Sequence[Trigger]:
    """Return trigger instances contributed by one provider plugin."""
    return ()
