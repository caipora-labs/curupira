"""Pluggy hook specifications for coding-agent providers.

Built-in providers and the core share this contract. Third-party coding agents continue
to register through the ``curupira.agents`` entry-point group and the public
``curupira.plugins`` API; they do not need to depend on Pluggy.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import pluggy

if TYPE_CHECKING:
    from curupira.agents.base import CodingAgentCliAdapter

PROJECT_NAME = "curupira"
hookspec = pluggy.HookspecMarker(PROJECT_NAME)
hookimpl = pluggy.HookimplMarker(PROJECT_NAME)


@hookspec
def curupira_coding_agent_adapters() -> Sequence[type[CodingAgentCliAdapter]]:
    """Return coding-agent adapter classes contributed by one provider plugin."""
