"""Entry-point discovery, configuration, persistence, and execution of agent plugins."""

from pathlib import Path

import pytest
from pydantic import ValidationError

import curupira.agents.registry as agent_registry
import curupira.plugins as plugins
from curupira.agents import create_cli_adapter
from curupira.cli import main
from curupira.config import ApplicationSettings
from curupira.errors import PluginLoadError
from curupira.models import CodingTaskRequest, RunningCodingSession
from curupira.tui.formatting import provider_label
from tests.helpers import issue_task
from tests.plugins.echo_agent_plugin import EchoCliAdapter, EchoCliProfile
from tests.plugins.entry_points import FakeDistribution, FakeEntryPoint, Install

MODULE = "tests.plugins.echo_agent_plugin"
DISTRIBUTION = FakeDistribution("curupira-echo", "0.4.0")


def agent_entry_point(name: str, value: str) -> FakeEntryPoint:
    return FakeEntryPoint(name, value, DISTRIBUTION, plugins.AGENT_ENTRY_POINT_GROUP)


@pytest.fixture
def echo(install: Install) -> type[EchoCliAdapter]:
    install(agent_entry_point("echo", f"{MODULE}:EchoCliAdapter"))
    adapter = agent_registry.get("echo")
    assert adapter is EchoCliAdapter
    return EchoCliAdapter


def echo_settings(**profile: object) -> ApplicationSettings:
    return ApplicationSettings.model_validate(
        {
            "coding_agents": {
                "defaults": {"profile": "echo"},
                "profiles": {"echo": {"provider": "echo", **profile}},
                "automations": {"work": {"repo": "acme/api", "query": "is:open", "prompt": "Fix"}},
            }
        }
    )


def write_echo_config(path: Path) -> Path:
    config = path / "settings.toml"
    config.write_text(
        """
[coding_agents.defaults]
profile = "echo"

[coding_agents.profiles.echo]
provider = "echo"
volume = "loud"

[coding_agents.automations.work]
trigger_type = "issue"
repo = "acme/api"
query = "is:open"
prompt = "Fix"
""",
        encoding="utf-8",
    )
    return config


def test_load_agent_plugins_registers_entry_points_once(install: Install) -> None:
    install(agent_entry_point("echo", f"{MODULE}:EchoCliAdapter"))

    loaded = plugins.load_agent_plugins()

    assert loaded == [plugins.LoadedAgentPlugin("echo", "curupira-echo", "0.4.0", "echo")]
    assert plugins.load_agent_plugins() is loaded
    assert plugins.loaded_agent_plugins() == loaded
    assert list(agent_registry.registered())[-1] == "echo"


def test_agent_plugins_do_not_load_trigger_entry_points(install: Install) -> None:
    install(FakeEntryPoint("echo", f"{MODULE}:EchoCliAdapter"))

    assert plugins.load_agent_plugins() == []
    with pytest.raises(ValueError, match="unknown coding agent provider: echo"):
        agent_registry.get("echo")


@pytest.mark.parametrize(
    ("value", "detail"),
    [
        ("tests.plugins.missing_module:Adapter", "ModuleNotFoundError"),
        (f"{MODULE}:NOT_AN_ADAPTER", "not a CodingAgentCliAdapter subclass"),
        (f"{MODULE}:echo_adapter", "not a CodingAgentCliAdapter subclass"),
        (f"{MODULE}:FutureEchoCliAdapter", "requires plugin API 2, Curupira provides 1"),
        (
            f"{MODULE}:DuplicateCursorCliAdapter",
            "coding agent provider already registered: cursor",
        ),
        (f"{MODULE}:MismatchedCliAdapter", "must default provider to 'mismatch'"),
    ],
)
def test_invalid_agent_plugins_raise_actionable_errors(
    install: Install, value: str, detail: str
) -> None:
    install(agent_entry_point("bad", value))

    with pytest.raises(PluginLoadError, match=detail) as raised:
        plugins.load_agent_plugins()

    assert "'bad' from curupira-echo" in str(raised.value)
    assert plugins._agents_loaded is None


def test_plugin_profile_is_validated_by_its_own_model(echo: type[EchoCliAdapter]) -> None:
    profile = echo_settings(volume="loud").resolve_automations()["work"].profile

    assert isinstance(profile, EchoCliProfile)
    assert profile.volume == "loud"
    with pytest.raises(ValidationError, match="volume"):
        echo_settings(volume="deafening")
    with pytest.raises(ValidationError, match="extra"):
        echo_settings(agent="reviewer")


def test_unknown_plugin_provider_is_rejected(install: Install) -> None:
    with pytest.raises(ValidationError, match="unknown coding agent provider: echo"):
        echo_settings()


def test_validate_accepts_plugin_provider(
    echo: type[EchoCliAdapter], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--config", str(write_echo_config(tmp_path)), "validate"]) == 0
    assert "Configuration is valid (1 automations" in capsys.readouterr().out


def test_validate_reports_provider_collision_as_configuration_error(
    install: Install, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    install(agent_entry_point("shadow", f"{MODULE}:DuplicateCursorCliAdapter"))

    assert main(["--config", str(write_echo_config(tmp_path)), "validate"]) == 2
    error = capsys.readouterr().err
    assert "Configuration error: could not load plugin 'shadow' from curupira-echo" in error
    assert "coding agent provider already registered: cursor" in error


def test_running_session_with_plugin_profile_round_trips(
    echo: type[EchoCliAdapter], tmp_path: Path
) -> None:
    task = issue_task(tmp_path)
    automation = task.automation.model_copy(update={"profile": EchoCliProfile(volume="loud")})
    session = RunningCodingSession(
        task=task.model_copy(update={"automation": automation}),
        session_id="native",
        message="Fix",
    )

    restored = RunningCodingSession.model_validate_json(session.model_dump_json())

    assert restored == session
    assert isinstance(restored.task.automation.profile, EchoCliProfile)
    assert restored.task.automation.profile.volume == "loud"


def test_create_cli_adapter_builds_plugin_arguments(
    echo: type[EchoCliAdapter], tmp_path: Path
) -> None:
    request = CodingTaskRequest(cwd=tmp_path, profile=EchoCliProfile(), message="Fix it")

    adapter = create_cli_adapter("echo")

    assert isinstance(adapter, EchoCliAdapter)
    assert adapter.build_arguments(request) == ("--volume", "quiet", "--", "Fix it")


def test_provider_label_uses_plugin_display_name(echo: type[EchoCliAdapter]) -> None:
    assert provider_label("echo") == "Echo Agent"
    assert provider_label("unregistered") == "unregistered"


def test_plugins_list_shows_agent_lines(
    echo: type[EchoCliAdapter], capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["plugins", "list"]) == 0

    lines = capsys.readouterr().out.splitlines()
    assert "agent:echo\tcurupira-echo 0.4.0\texecutable: echo-agent" in lines
    assert any(
        line.startswith("agent:cursor\tcurupira ")
        and line.endswith("(built-in)\texecutable: agent")
        for line in lines
    )
    trigger_lines = [line for line in lines if not line.startswith("agent:")]
    assert lines[: len(trigger_lines)] == trigger_lines


def test_plugins_list_reports_agent_load_failures(
    install: Install, capsys: pytest.CaptureFixture[str]
) -> None:
    install(agent_entry_point("bad", f"{MODULE}:NOT_AN_ADAPTER"))

    assert main(["plugins", "list"]) == 1
    assert "Plugin error: could not load plugin 'bad'" in capsys.readouterr().err
