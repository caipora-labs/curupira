"""MkDocs macros render provider data from the coding-agent registry."""

import tomllib
from collections.abc import Callable
from typing import IO

import pytest

import curupira.agents.registry as agent_registry
import main
from tests.plugins.echo_agent_plugin import EchoCliAdapter

STALE_PROFILE_URL = "https://stale.example/optional-profile"


class RecordingMacroEnvironment:
    """Collect the macros registered by ``define_env``."""

    def __init__(self) -> None:
        self.macros: dict[str, Callable[[], str]] = {}

    def macro(self, function: Callable[[], str]) -> Callable[[], str]:
        self.macros[function.__name__] = function
        return function


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    agent_registry.registered()
    monkeypatch.setattr(agent_registry, "_ADAPTERS", dict(agent_registry._ADAPTERS))


@pytest.fixture
def macros(monkeypatch: pytest.MonkeyPatch) -> dict[str, Callable[[], str]]:
    real_load = tomllib.load

    def load_with_stale_profiles(file: IO[bytes]) -> dict[str, object]:
        data = real_load(file)
        data["optional_profiles"] = [{"name": "Stale", "url": STALE_PROFILE_URL}]
        return data

    monkeypatch.setattr(main.tomllib, "load", load_with_stale_profiles)
    env = RecordingMacroEnvironment()
    main.define_env(env)
    return env.macros


def _table_rows(table: str) -> list[str]:
    return table.splitlines()[2:]


def test_providers_table_has_one_row_per_built_in(macros: dict[str, Callable[[], str]]) -> None:
    adapters = agent_registry.registered()
    rows = _table_rows(macros["providers_table"]())

    assert rows == [
        f"| [{adapter.display_name}](providers/{provider}.md) | `{adapter.executable}` "
        f"| <{adapter.install_url}> |"
        for provider, adapter in adapters.items()
    ]
    cursor = adapters["cursor"]
    assert (
        f"| [{cursor.display_name}](providers/cursor.md) | `{cursor.executable}` "
        f"| <{cursor.install_url}> |"
    ) in rows


def test_requirements_list_reads_install_urls_from_registry(
    macros: dict[str, Callable[[], str]],
) -> None:
    requirements = macros["requirements_list"]()

    for adapter in agent_registry.registered().values():
        assert (
            f"  - [{adapter.display_name} (`{adapter.executable}`)]({adapter.install_url})"
            in requirements
        )
    assert STALE_PROFILE_URL not in requirements
    assert "[GitHub CLI (`gh`)](https://cli.github.com/)" in requirements


def test_registered_plugin_adapter_appears_in_both_macros(
    macros: dict[str, Callable[[], str]],
) -> None:
    agent_registry.register(EchoCliAdapter)

    assert _table_rows(macros["providers_table"]())[-1] == (
        "| [Echo Agent](providers/echo.md) | `echo-agent` | <https://echo.example/> |"
    )
    assert "  - [Echo Agent (`echo-agent`)](https://echo.example/)" in (
        macros["requirements_list"]()
    )
