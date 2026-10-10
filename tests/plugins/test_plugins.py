"""Entry-point discovery, configuration, persistence, and execution of trigger plugins."""

from pathlib import Path

import pytest
from pydantic import ValidationError

import curupira.plugins as plugins
import curupira.tasks.registry as registry
from curupira.cli import main
from curupira.config import ApplicationSettings, load_settings
from curupira.dispatcher import create_task_feeds
from curupira.errors import PluginLoadError
from curupira.executor import TaskExecutor, render_task_prompt
from curupira.models import RunningCodingSession, Task, TaskIdentity
from curupira.storage import CronScheduleRepository, RunningSessionRepository
from tests.fakes import FakeVersionControl, RecordingAdapter
from tests.plugins.entry_points import FakeEntryPoint, Install
from tests.plugins.ticket_plugin import TicketAutomationConfiguration, TicketItem, TicketTrigger

MODULE = "tests.plugins.ticket_plugin"


@pytest.fixture
def ticket(install: Install) -> TicketTrigger:
    install(FakeEntryPoint("ticket", f"{MODULE}:TicketTrigger"))
    trigger = registry.get("ticket")
    assert isinstance(trigger, TicketTrigger)
    return trigger


def ticket_settings(path: Path, **overrides: object) -> ApplicationSettings:
    from tests.helpers import settings_dict

    automation: dict[str, object] = {
        "trigger_type": "ticket",
        "repository": "api",
        "project": "OPS",
        "priority": "high",
        "prompt": "Fix ${ticket_key} (${ticket_priority}) in ${repository}",
    }
    automation.update(overrides)
    return ApplicationSettings.model_validate(
        settings_dict(
            {"tickets": automation},
            repositories={
                "api": {
                    "remote": "https://github.com/acme/api.git",
                    "path": str(path),
                }
            },
            settings={"state_db_path": str(path / "state.sqlite3")},
        )
    )


def ticket_task(settings: ApplicationSettings, key: str = "OPS-7") -> Task:
    automation = settings.resolve_automations()["tickets"]
    return Task(
        identity=TaskIdentity(automation_id="tickets", repo="api", task_type="ticket", id=key),
        automation=automation,
        title=f"Ticket {key}",
        url=f"https://tracker.example/OPS/{key}",
        item=TicketItem(ticket_key=key, ticket_priority="high"),
    )


def test_load_plugins_registers_entry_points_once(install: Install) -> None:
    install(FakeEntryPoint("ticket", f"{MODULE}:TicketTrigger"))

    loaded = plugins.load_plugins()

    assert loaded == [plugins.LoadedPlugin("ticket", "curupira-ticket", "1.2.3", "ticket")]
    assert plugins.load_plugins() is loaded
    assert isinstance(registry.get("ticket"), TicketTrigger)
    assert list(registry.registered())[-1] == "ticket"


def test_entry_point_may_export_a_trigger_instance(install: Install) -> None:
    from tests.plugins.ticket_plugin import ticket_trigger

    install(FakeEntryPoint("ticket", f"{MODULE}:ticket_trigger", dist=None))

    assert plugins.loaded_plugins() == [
        plugins.LoadedPlugin("ticket", "unknown", "unknown", "ticket")
    ]
    assert registry.get("ticket") is ticket_trigger


@pytest.mark.parametrize(
    ("value", "detail"),
    [
        ("tests.plugins.missing_module:Trigger", "ModuleNotFoundError"),
        (f"{MODULE}:NOT_A_TRIGGER", "not a Trigger subclass or instance"),
        (f"{MODULE}:BrokenTrigger", "tracker token missing"),
        (f"{MODULE}:FutureTrigger", "requires plugin API 3, Curupira provides 2"),
        (f"{MODULE}:DuplicateIssueTrigger", "trigger type already registered: github-issues"),
    ],
)
def test_invalid_plugins_raise_actionable_errors(install: Install, value: str, detail: str) -> None:
    install(FakeEntryPoint("bad", value))

    with pytest.raises(PluginLoadError, match=detail) as raised:
        plugins.load_plugins()

    assert "'bad' from curupira-ticket" in str(raised.value)
    assert plugins._loaded is None


def test_plugin_configuration_is_validated_by_its_own_model(
    ticket: TicketTrigger, tmp_path: Path
) -> None:
    automation = ticket_settings(tmp_path).automations["tickets"]

    assert isinstance(automation, TicketAutomationConfiguration)
    assert (automation.project, automation.priority) == ("OPS", "high")
    with pytest.raises(ValidationError, match="priority"):
        ticket_settings(tmp_path, priority="urgent")
    with pytest.raises(ValidationError, match="project"):
        ticket_settings(tmp_path, project=None)
    with pytest.raises(ValidationError, match="unsupported prompt placeholders"):
        ticket_settings(tmp_path, prompt="${issue_number}")


def test_unknown_plugin_trigger_type_is_rejected(install: Install, tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="unknown trigger type: ticket"):
        ticket_settings(tmp_path)


def test_non_string_trigger_type_is_rejected(install: Install, tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="trigger_type must be a string"):
        ticket_settings(tmp_path, trigger_type=7)


async def test_plugin_fields_survive_toml_loading(ticket: TicketTrigger, tmp_path: Path) -> None:
    config = tmp_path / "settings.toml"
    config.write_text(
        """
[repositories.api]
remote = "https://github.com/acme/api.git"
path = "checkout"

[agents.defaults]
profile = "opencode"

[agents.profiles.opencode]
provider = "opencode"

[automations.tickets]
trigger_type = "ticket"
repository = "api"
project = "OPS"
prompt = "Fix ${ticket_key}"
""",
        encoding="utf-8",
    )

    settings = await load_settings(config)

    automation = settings.resolve_automations()["tickets"]
    assert isinstance(automation.configuration, TicketAutomationConfiguration)
    assert automation.configuration.project == "OPS"
    assert automation.workspace_path == (tmp_path / "checkout").resolve()


async def test_plugin_task_snapshot_round_trips_through_sqlite(
    ticket: TicketTrigger, tmp_path: Path
) -> None:
    task = ticket_task(ticket_settings(tmp_path))
    sessions = RunningSessionRepository(tmp_path / "state.sqlite3")

    await sessions.save(RunningCodingSession(task=task, session_id="native", message="Fix"))
    restored = await sessions.get(task)

    assert restored is not None
    assert restored.task == task
    assert isinstance(restored.task.automation.configuration, TicketAutomationConfiguration)
    assert restored.task.item == TicketItem(ticket_key="OPS-7", ticket_priority="high")


def test_plugin_prompt_uses_typed_item(ticket: TicketTrigger, tmp_path: Path) -> None:
    assert render_task_prompt(ticket_task(ticket_settings(tmp_path))) == ("Fix OPS-7 (high) in api")


def test_plugin_rejects_scheduled_occurrence_by_default(
    ticket: TicketTrigger, tmp_path: Path
) -> None:
    task = ticket_task(ticket_settings(tmp_path))

    with pytest.raises(ValidationError, match="must not contain a scheduled occurrence"):
        Task.model_validate({**task.model_dump(), "scheduled_for": "2026-10-01T00:00:00Z"})


async def test_plugin_feed_discovers_tasks(ticket: TicketTrigger, tmp_path: Path) -> None:
    ticket.tickets = [("OPS-1", "low"), ("OPS-2", "high")]
    settings = ticket_settings(tmp_path)

    feeds = create_task_feeds(settings, CronScheduleRepository(settings.settings.state_db_path))
    tasks = await feeds[0].poll()

    assert [task.identity.id for task in tasks] == ["OPS-1", "OPS-2"]
    assert tasks[1].item == TicketItem(ticket_key="OPS-2", ticket_priority="high")


async def test_executor_uses_plugin_hooks_and_version_control(
    ticket: TicketTrigger, tmp_path: Path
) -> None:
    settings = ticket_settings(tmp_path)
    plugin_vcs = FakeVersionControl()
    ticket.version_control = plugin_vcs
    sessions = RunningSessionRepository(settings.settings.state_db_path)
    adapter = RecordingAdapter()
    executor = TaskExecutor(
        settings.settings,
        None,
        sessions,
        CronScheduleRepository(settings.settings.state_db_path),
        adapter_factory=lambda _: adapter,
    )

    result = await executor.execute(ticket_task(settings))

    assert result.returncode == 0
    assert adapter.requests[0].message == "Fix OPS-7 (high) in api"
    assert plugin_vcs.checkouts == [tmp_path]
    assert ticket.events == ["started:OPS-7", "finished:OPS-7"]
    assert await sessions.list_all() == []


def test_plugins_list_shows_origin_and_prompt_fields(
    ticket: TicketTrigger, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["plugins", "list"]) == 0

    output = capsys.readouterr().out
    assert "ticket\tcurupira-ticket 1.2.3\tprompt fields: ticket_key, ticket_priority" in output
    assert "cron\tcurupira " in output
    assert "(built-in)\tprompt fields: -" in output


def test_plugins_list_reports_load_failures(
    install: Install, capsys: pytest.CaptureFixture[str]
) -> None:
    install(FakeEntryPoint("bad", f"{MODULE}:NOT_A_TRIGGER"))

    assert main(["plugins", "list"]) == 1
    assert "Plugin error: could not load plugin 'bad'" in capsys.readouterr().err


def test_validate_reports_plugin_failures_as_configuration_errors(
    install: Install, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    install(FakeEntryPoint("bad", f"{MODULE}:NOT_A_TRIGGER"))
    config = tmp_path / "settings.toml"
    config.write_text(
        '[repositories.api]\nremote = "https://github.com/acme/api.git"\n'
        '[agents.defaults]\nprofile = "opencode"\n'
        '[agents.profiles.opencode]\nprovider = "opencode"\n'
        '[automations.work]\ntrigger_type = "github-issues"\nrepository = "api"\n'
        'repo = "acme/api"\nlabels = ["agent-ready"]\nprompt = "Fix"\n',
        encoding="utf-8",
    )

    assert main(["--config", str(config), "validate"]) == 2
    assert "Configuration error: could not load plugin 'bad'" in capsys.readouterr().err
