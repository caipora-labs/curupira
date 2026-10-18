# Ejecutar Curupira

Todos los comandos leen el mismo archivo de configuración y usan el mismo flujo de despacho.
El alias corto `curu` acepta todos los comandos.

## Comandos { #commands }

| Comando | Qué hace |
| --- | --- |
| `curupira validate` | Verifica el TOML, las referencias, los plugins y los prompts. No ejecuta ninguna automatización ni escribe estado. |
| `curupira run` | Ejecuta las tareas disponibles en este momento y luego sale. |
| `curupira run --size N` | Lo mismo, pero admite como máximo `N` tareas. |
| `curupira run --dry-run` | Imprime la primera tarea que se ejecutaría y su prompt renderizado. No clona nada ni inicia ningún agente. |
| `curupira run --watch` | Sigue consultando y ejecutando tareas hasta que lo interrumpas. |
| `curupira tui` | El ciclo continuo desde el punto de entrada del [panel en la terminal](tui.md). |
| `curupira plugins …` | Lista e inspecciona los [plugins y triggers](extensions.md#manage) disponibles. |

`--dry-run`, `--watch` y `--size` no se pueden combinar; si lo intentas, Curupira sale con
el código `2`.

Las opciones globales van antes del comando:

```sh
curupira --config ./settings-dev.toml validate
curupira --config ./settings-dev.toml run --watch
curupira --log-level DEBUG run --watch
curupira --version
```

`--config` usa `~/.curupira/settings.toml` por defecto. `--log-level` reemplaza
`[settings].log_level` para un proceso (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).

## Salida { #output }

`run` imprime una línea por cada tarea terminada, separada por un tabulador:

```text
ok      resolve-ready-issues:acme/api:plugins-py/github-issues:9c1e…
fail    review-ready-prs:acme/api:plugins-py/github-pull-requests:41ad…  agent exited 1: …
```

La segunda columna es la identidad de la tarea: automatización, repositorio, trigger y un
hash de los campos del elemento. Las líneas `ok` van a stdout y las líneas `fail` a stderr,
así que puedes redirigirlas por separado.

`run --dry-run` imprime la identidad y el prompt exacto que recibiría el agente:

```text
dry-run resolve-ready-issues:acme/api:plugins-py/github-issues:9c1e…
--- prompt ---
Resolve issue #128: Retry flaky webhook deliveries
…
--- end prompt ---
```

## Códigos de salida { #exit-codes }

| Código | Significado |
| --- | --- |
| `0` | Éxito. Para `run`, cada tarea ejecutada terminó `ok`. |
| `1` | Al menos una tarea falló, o un error de plugin o de ejecución detuvo la ejecución. |
| `2` | Error de configuración (TOML inválido, referencia desconocida, flags en conflicto). |
| `130` | Interrumpido con ++ctrl+c++. |

## Planificación { #scheduling }

- Hasta `[settings].max_active_tasks` tareas se ejecutan al mismo tiempo (por defecto `1`).
- En el modo `--watch`, Curupira consulta cada automatización cada
  `[settings.polling].poll_interval_seconds` (por defecto `30`).
- Una tarea que terminó `ok` queda registrada en la base de datos de estado y nunca vuelve
  a ejecutarse.
- Una tarea que falla no se reintenta en el mismo proceso. El siguiente `run` (o un
  `--watch` reiniciado) la intenta de nuevo.
- Cada ejecución del agente está limitada por `[settings].task_timeout_minutes` (por defecto `20`).

## Un proceso a la vez { #lock }

`run` y `tui` mantienen `~/.curupira/dispatch.lock` mientras trabajan. Un segundo proceso
que intenta despachar falla de inmediato en lugar de competir con el primero. `validate`,
`run --dry-run` y `plugins` no toman el lock.

## Reanudar sesiones { #resume }

Cuando un agente anuncia un id de sesión (o Curupira asigna uno), se guarda con la tarea.
Si el proceso se detiene antes de que la tarea termine, la siguiente ejecución reanuda esa
sesión y le pide al agente que continúe el trabajo anterior en lugar de empezar de nuevo.
La sesión se elimina cuando la tarea termina `ok`.

## Cambiar la configuración { #reload }

Curupira lee la configuración una vez cuando empieza un comando. Después de editar
`settings.toml`, ejecuta `curupira validate` y luego reinicia `run --watch` o `tui` para
aplicar el cambio. Las tareas en ejecución terminan con los ajustes con los que empezaron.
