# Plugins

Los plugins añaden nuevas fuentes de automatización (tipos de trigger) sin modificar
Curupira. Un plugin es una distribución de Python común, instalada junto a Curupira, que
declara un entry point por trigger. Sus automatizaciones se configuran en el mismo archivo
TOML, se validan al cargar la configuración y pasan por la misma planificación, checkout y
ejecución del coding agent que los triggers integrados.

El código de un plugin se ejecuta dentro del proceso de Curupira en cuanto se descubre.
Instala solo distribuciones en las que confíes.

## Usar un plugin

Instala el plugin en el mismo entorno que Curupira y comprueba que se haya cargado:

```bash
uv tool install curupira --with curupira-tickets
curu plugins list
```

`curu plugins list` muestra cada tipo de trigger, la distribución que lo proporciona y los
placeholders de prompt que añade. Configura la automatización con ese `trigger_type` y las
opciones documentadas por el plugin:

```toml
[coding_agents.automations.ops-tickets]
trigger_type = "ticket"
repo = "acme/api"
project = "OPS"
prompt = "Corrige ${ticket_key} (${ticket_priority}) en ${repo}"
```

`curu validate` comprueba las opciones y los placeholders del plugin igual que con los
integrados. Si un plugin no se puede importar, todo comando que carga la configuración se
detiene con un `Configuration error` que indica el entry point y la distribución.

## Escribir un plugin

Un plugin proporciona tres piezas, todas importadas de `curupira.plugins`:

1. Un modelo de configuración que extiende `AutomationConfigurationBase` y usa como valor
   por defecto de `trigger_type` el tipo del plugin. Hereda `repo`, `path`, `setup_script`,
   `checkout`, `prompt` y `profile`, y añade las opciones del plugin como campos y
   validadores de Pydantic.
2. Un `TaskSource`, que convierte una consulta en objetos `Task`. Envuélvelo en
   `PollingTaskFeed` para obtener deduplicación y backoff sin esfuerzo.
3. Un `Trigger`, que une el modelo de configuración, los placeholders de prompt y el feed.

El ejemplo de código completo está en la [página en inglés](../en/plugins.md#writing-a-plugin);
los nombres de clases y campos son los mismos.

Registra el trigger en el `pyproject.toml` del plugin. El entry point puede apuntar a la
subclase de `Trigger` (instanciada sin argumentos) o a una instancia ya creada:

```toml
[project]
name = "curupira-tickets"
dependencies = ["curupira"]

[project.entry-points."curupira.triggers"]
ticket = "curupira_tickets:TicketTrigger"
```

### Contrato

| Miembro | Obligatorio | Función |
| --- | --- | --- |
| `trigger_type` | Sí | Valor usado en `trigger_type`; debe ser único entre integrados y plugins. |
| `configuration_model` | Sí | Modelo de Pydantic de la tabla de la automatización. |
| `prompt_fields()` | Sí | Placeholders que el trigger añade a los comunes. |
| `prompt_context(task)` | Sí | Valores de esos placeholders. |
| `build_feed(automation, dependencies)` | Sí | Feed que descubre las tareas. |
| `validate_task(task)` | No | Rechaza snapshots de tareas que el trigger no podría haber generado. |
| `create_version_control(runner)` | No | Mecanismo de clonado de los repositorios; `None` mantiene `gh repo clone`. |
| `on_task_started(task, state)` | No | Se ejecuta justo antes de que empiece el coding agent. |
| `on_task_finished(task, state)` | No | Libera el estado cuando el agente termina; por defecto borra la sesión reanudable, así que llama a `super()` al sobrescribirlo. |
| `api_version` | No | Versión de la API de plugins que usa el plugin; por defecto es el `PLUGIN_API_VERSION` del Curupira en ejecución. Defínela explícitamente para fallar pronto ante una versión incompatible. |

`FeedDependencies` expone `polling`, `state_db_path` y `runner`. Inicia procesos externos
solo mediante `runner` (un `AsyncProcessRunner` que recibe un `CommandRequest`), nunca a
través de un shell. Guarda los valores específicos de la fuente en `Task.attributes`, un
mapeo de strings que se persiste con la tarea, para que el prompt se siga renderizando
cuando se reanude una tarea interrumpida.

Curupira rechaza un plugin cuyo `api_version` sea distinto de `PLUGIN_API_VERSION`, cuyo
`trigger_type` ya esté registrado o cuyo `configuration_model` no use el tipo registrado
como valor por defecto de `trigger_type`.

### Probar un plugin

Se puede probar el plugin sin instalarlo: registra el trigger con
`curupira.tasks.registry.register`, valida una configuración con
`ApplicationSettings.model_validate` y llama al trigger directamente. La suite de Curupira
incluye un plugin de ejemplo completo en `tests/plugins/ticket_plugin.py` y las pruebas
correspondientes en `tests/plugins/test_plugins.py`.

La referencia generada de los modelos está en la [página en inglés](../en/plugins.md#reference).
