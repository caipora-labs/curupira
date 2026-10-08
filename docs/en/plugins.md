# Plugins

Plugins add new automation sources (trigger types) without changing Curupira. A plugin
is an ordinary Python distribution that installs next to Curupira and declares one entry
point per trigger. Its automations are configured in the same TOML file, validated when
the configuration loads, and run through the same scheduling, checkout, and coding-agent
pipeline as the built-in triggers.

Plugins run in the Curupira process as soon as they are discovered, so install only
distributions you trust.

## Using a plugin

Install the plugin into the same environment as Curupira, then confirm that it loaded:

```bash
uv tool install curupira --with curupira-tickets
curu plugins list
```

`curu plugins list` prints each trigger type, the distribution that provides it, and the
prompt placeholders it supplies. Configure the automation with that `trigger_type` plus
the options documented by the plugin:

```toml
[coding_agents.automations.ops-tickets]
trigger_type = "ticket"
repo = "acme/api"
project = "OPS"
prompt = "Fix ${ticket_key} (${ticket_priority}) in ${repo}"
```

`curu validate` checks plugin options and placeholders exactly like built-in ones. If a
plugin cannot be imported, every command that loads the configuration stops with a
`Configuration error` that names the entry point and the distribution.

## Writing a plugin

A plugin provides three things, all imported from `curupira.plugins`:

1. A configuration model that extends `AutomationConfigurationBase` and gives
   `trigger_type` a default equal to the plugin's trigger type. It inherits `repo`,
   `path`, `setup_script`, `checkout`, `prompt`, and `profile`, and adds the plugin's
   own options as Pydantic fields and validators.
2. A `TaskSource` that turns one poll into `Task` objects. Wrap it in
   `PollingTaskFeed` to get deduplication and backoff for free.
3. A `Trigger` that ties the configuration model, prompt placeholders, and feed together.

```python
"""Ticket tracker trigger for Curupira."""

from typing import Literal

from curupira.plugins import (
    AutomationConfigurationBase,
    FeedDependencies,
    NonEmptyString,
    PollingTaskFeed,
    ResolvedAutomation,
    Task,
    TaskFeed,
    TaskIdentity,
    TaskSource,
    Trigger,
)


class TicketAutomationConfiguration(AutomationConfigurationBase):
    """Discover tickets from one tracker project.

    Attributes:
        project: Tracker project key.
    """

    trigger_type: Literal["ticket"] = "ticket"
    project: NonEmptyString


class TicketSource(TaskSource):
    """List open tickets through the tracker's CLI."""

    async def discover(self, automation: ResolvedAutomation, limit: int) -> list[Task]:
        config = automation.configuration
        if not isinstance(config, TicketAutomationConfiguration):
            raise ValueError("ticket source requires a ticket configuration")
        tickets = ...  # call the tracker through FeedDependencies.runner
        return [
            Task(
                identity=TaskIdentity(
                    automation_id=automation.automation_id,
                    repo=config.repo,
                    task_type="ticket",
                    id=ticket.key,
                ),
                automation=automation,
                title=ticket.summary,
                body=ticket.description,
                url=ticket.url,
                attributes={"priority": ticket.priority},
            )
            for ticket in tickets[:limit]
        ]


class TicketTrigger(Trigger):
    """Run coding agents for tracker tickets."""

    trigger_type = "ticket"
    configuration_model = TicketAutomationConfiguration

    @classmethod
    def prompt_fields(cls) -> frozenset[str]:
        return frozenset({"ticket_key", "ticket_priority"})

    def prompt_context(self, task: Task) -> dict[str, str]:
        return {"ticket_key": task.identity.id, "ticket_priority": task.attributes["priority"]}

    def build_feed(
        self, automation: ResolvedAutomation, dependencies: FeedDependencies
    ) -> TaskFeed:
        return PollingTaskFeed(automation, dependencies.polling, TicketSource())
```

Register the trigger in the plugin's `pyproject.toml`. The entry point may name the
`Trigger` subclass (instantiated without arguments) or a ready-made instance:

```toml
[project]
name = "curupira-tickets"
dependencies = ["curupira"]

[project.entry-points."curupira.triggers"]
ticket = "curupira_tickets:TicketTrigger"
```

### Contract

| Member | Required | Purpose |
| --- | --- | --- |
| `trigger_type` | Yes | Value users write in `trigger_type`; must be unique across built-ins and plugins. |
| `configuration_model` | Yes | Pydantic model for the automation table. |
| `prompt_fields()` | Yes | Placeholders the trigger adds on top of the common ones. |
| `prompt_context(task)` | Yes | Values for those placeholders. |
| `build_feed(automation, dependencies)` | Yes | Feed that discovers tasks. |
| `validate_task(task)` | No | Rejects task snapshots the trigger could not produce. |
| `create_version_control(runner)` | No | Clone mechanism for the repositories; `None` keeps `gh repo clone`. |
| `on_task_started(task, state)` | No | Runs right before the coding agent starts. |
| `on_task_finished(task, state)` | No | Releases state after the agent exits; the default deletes the resumable session, so call `super()` when you override it. |
| `api_version` | No | Plugin API version the plugin targets; defaults to the running Curupira's `PLUGIN_API_VERSION`. Set it explicitly to fail fast on an incompatible Curupira release. |

`FeedDependencies` exposes `polling`, `state_db_path`, and `runner`. Start external
processes only through `runner` (an `AsyncProcessRunner` taking a `CommandRequest`),
never through a shell. Put source-specific values in `Task.attributes`, a string mapping
that is persisted with the task, so prompts still render after an interrupted task resumes.

Curupira rejects a plugin whose `api_version` differs from `PLUGIN_API_VERSION`, whose
`trigger_type` is already registered, or whose `configuration_model` does not default
`trigger_type` to the registered type.

### Testing a plugin

Exercise the plugin without installing it by validating a configuration and calling the
trigger directly:

```python
from curupira.config import ApplicationSettings
from curupira.tasks.registry import register

register(TicketTrigger())
settings = ApplicationSettings.model_validate(
    {
        "coding_agents": {
            "automations": {
                "tickets": {
                    "trigger_type": "ticket",
                    "repo": "acme/api",
                    "project": "OPS",
                    "prompt": "Fix ${ticket_key}",
                }
            }
        }
    }
)
```

Curupira's own suite contains a complete example plugin in
`tests/plugins/ticket_plugin.py` and the matching tests in `tests/plugins/test_plugins.py`.

## Reference

::: curupira.tasks.base.Trigger

::: curupira.tasks.base.FeedDependencies

::: curupira.tasks.base.TriggerState

::: curupira.models.configuration.AutomationConfigurationBase
