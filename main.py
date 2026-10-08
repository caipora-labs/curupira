"""MkDocs macros for rendering versioned documentation data."""

import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from curupira.agents import registry


class MacroEnvironment(Protocol):
    """Interface provided by the MkDocs macros plugin."""

    def macro(self, function: Callable[[], str]) -> Callable[[], str]:
        """Register a zero-argument string-producing macro."""


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
            for adapter in registry.registered().values()
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
            for provider, adapter in registry.registered().items()
        )
        return "\n".join(lines)
