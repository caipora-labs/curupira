# Configuración

Curupira lee un único archivo TOML, `~/.curupira/settings.toml` por defecto (`--config`
elige otro). Tiene seis tipos de tablas:

| Tabla | Qué declara |
| --- | --- |
| `[settings]` | Límites de ejecución, rutas y polling |
| `[environment]` | Variables copiadas a cada proceso que Curupira inicia |
| `[repositories.<alias>]` | Los remotos de Git donde trabajan los agentes |
| `[agents]` | El perfil predeterminado y una tabla por cada perfil de agente |
| `[plugins.<alias>]` | Paquetes de fuentes de tareas y cómo iniciarlos |
| `[automations.<name>]` | Qué vigilar, dónde trabajar, qué agente y el prompt |

Los nombres después del punto (`api`, `claude`, `plugins-py`, `resolve-ready-issues`) los
eliges tú. Ejecuta `curupira validate` después de cada cambio.

## Un archivo completo { #example }

```toml
[settings]
max_active_tasks = 1
workspace_dir = "~/.curupira/workspaces"
state_db_path = "~/.curupira/state.sqlite3"
log_level = "INFO"
task_timeout_minutes = 20

[settings.polling]
poll_interval_seconds = 30
batch_size = 100

[environment.vars]
# HTTPS_PROXY = "http://proxy.internal:8080"

[repositories.api]
remote = "https://github.com/acme/api.git"
# path = "~/code/api"
# setup_script = "scripts/bootstrap.sh"

[agents.defaults]
profile = "opencode-default"
timezone = "UTC"

[agents.profiles.opencode-default]
provider = "opencode"

[plugins.plugins-py]
type = "uvx"
args = ["--from", "curupira-plugins", "curupira-plugins"]
tools = ["*"]

[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
linked_pull_request = false
prompt = "Resolve issue ${issue_number}: ${issue_title}\n\n${issue_body}"
```

## Ajustes { #settings }

Todas las claves son opcionales.

| Clave | Valor predeterminado | Significado |
| --- | --- | --- |
| `max_active_tasks` | `1` | Agentes que pueden ejecutarse al mismo tiempo. |
| `workspace_dir` | `~/.curupira/workspaces` | Dónde se clonan los repositorios. |
| `state_db_path` | `~/.curupira/state.sqlite3` | Ocurrencias de cron y sesiones reanudables del agente; ningún historial de issues ni pull requests. |
| `log_level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` o `CRITICAL`. `--log-level` lo reemplaza. |
| `task_timeout_minutes` | `20` | Plazo máximo de una ejecución del agente y de `setup_script`. |
| `max_output_bytes` | `1000000` | Salida que se conserva de cada ejecución del agente y del script de setup. |
| `polling.poll_interval_seconds` | `30` | Pausa entre consultas en `run --watch` y `tui`. |
| `polling.batch_size` | `100` | Elementos pedidos a cada trigger por consulta. |

Las rutas relativas se resuelven respecto al directorio del archivo de configuración.

## Entorno { #environment }

Todo proceso que Curupira inicia — agentes de código, Git, `setup_script` y extensiones — recibe una copia de cada variable de entorno que el proceso Curupira puede ver. `[environment.vars]` sustituye esos valores. Omite la tabla para pasar el entorno del proceso sin cambios.

Los valores son cadenas literales. `$VAR` y `${VAR}` no se expanden.

Curupira sigue fijando el directorio de trabajo (`PWD`) y quitando las variables que atan un repositorio (`GIT_DIR` y los demás vínculos `GIT_*`) después de esas sobrescrituras, y las variables propias de un agente (por ejemplo `OPENCODE_DB`) se aplican después de `[environment.vars]`.

```toml
[environment.vars]
HTTPS_PROXY = "http://proxy.internal:8080"
GITHUB_TOKEN = "ghp_..."
```

| Clave | Significado |
| --- | --- |
| `vars` | Nombres de variables de entorno y los valores que las sustituyen. Vacío cuando se omite. Los nombres siguen `[A-Za-z_][A-Za-z0-9_]*`. |

## Repositorios { #repositories }

`[repositories.<alias>]` es un checkout de Git donde trabajan una o más automatizaciones.

| Clave | Obligatoria | Significado |
| --- | --- | --- |
| `remote` | sí | La URL para `git clone`: HTTPS, SSH o `user@host:path`. |
| `path` | no | Usa o crea el checkout aquí en lugar de `workspace_dir/<alias>`. |
| `setup_script` | no | Un ejecutable relativo al repositorio que se ejecuta una vez, justo después de un clon nuevo. |

El remoto no tiene que estar en GitHub: el filtro `repo` del trigger decide qué se vigila,
y `remote` decide dónde trabaja el agente. Los clones usan tus credenciales de Git
habituales.

## Agentes { #agents }

```toml
[agents.defaults]
profile = "claude"    # lo usan las automatizaciones que no definen un perfil
timezone = "UTC"      # zona horaria predeterminada para las automatizaciones cron

[agents.profiles.claude]
provider = "claude"
model = "sonnet"
```

Cada perfil define un `provider`: `claude`, `codex`, `copilot`, `cursor`, `gemini`, `kilo`,
`opencode`, `pi` o `qwen`. Las demás claves son opciones de ese agente; consulta
[Agentes de código](providers.md) para ver cada opción y el flag nativo en que se convierte.

## Asistente { #assistant }

`[assistant]` es opcional y está reservada para el asistente interactivo del
[panel en la terminal](tui.md#assistant).

| Clave | Significado |
| --- | --- |
| `agent` | Un nombre de proveedor integrado. `curupira validate` rechaza los nombres desconocidos. |
| `model` | Un id de modelo para ese agente. Omítelo para usar el valor predeterminado del agente. |

## Plugins { #plugins }

`[plugins.<alias>]` registra un paquete de triggers y cómo iniciarlo. Luego las
automatizaciones usan `trigger_type = "<alias>/<trigger>"`.

```toml
[plugins.plugins-py]
type = "uvx"
args = ["--from", "curupira-plugins", "curupira-plugins"]
tools = ["github-*"]

[plugins.acme-node]
type = "npx"
args = ["--yes", "@acme/curupira-ext@1.2.3"]
tools = ["*", "!internal-*"]
```

| Clave | Obligatoria | Significado |
| --- | --- | --- |
| `type` | sí | `uvx` o `npx`. Ese lanzador debe estar en el `PATH`. |
| `args` | sí | Argumentos después del lanzador, pasados como lista y nunca a través de un shell. Fija las versiones. |
| `tools` | no | Patrones glob que seleccionan triggers. `!` excluye. Vacío conserva todos los triggers. |

Los conectores como GitHub, y los que están en desarrollo, se listan en
[Plugins y conectores](plugins.md). Para escribir los tuyos, consulta
[Desarrollar extensiones](extensions.md) y el [SDK de JavaScript](extensions-javascript.md).

## Automatizaciones { #automations }

`[automations.<name>]` une un trigger con un repositorio, un agente y un prompt.

| Clave | Obligatoria | Significado |
| --- | --- | --- |
| `trigger_type` | sí | `<alias>/<trigger>` de un plugin, o `cron`. |
| `repository` | sí | Un nombre de `[repositories.<alias>]`. |
| `prompt` | sí | El mensaje para el agente. Consulta [Cómo escribir prompts](prompts.md). |
| `profile` | no | Un nombre de perfil. Por defecto, `[agents.defaults].profile`. |
| `checkout` | no | `worktree` (por defecto) o `main`. Consulta [Checkout y setup](#checkout). |

Todas las demás claves se pasan al trigger como sus ajustes. El trigger de GitHub recibe
`repo`, `labels` y otros filtros, documentados en [Issues y pull requests](github.md) y
[Projects](github-projects.md). Cron recibe `schedule` y las claves descritas en
[Cron](automations.md#cron).

Las automatizaciones se consultan en el orden del archivo. Los placeholders y las
condiciones del prompt se explican en [Cómo escribir prompts](prompts.md);
[Referencia de campos del prompt](prompt-fields.md) lista lo que proporciona cada trigger.

## Checkout y setup { #checkout }

Por defecto, cada tarea recibe su propio worktree y su rama junto al clon
(`<clone>.worktrees/<automation>/…`, rama `curupira/<automation>/…`). El worktree se
elimina cuando la tarea termina, así que las tareas nunca comparten archivos.

`checkout = "main"` ejecuta el agente en el clon compartido. En ese modo, Curupira no hace
fetch, pull ni cambia de rama; úsalo para trabajos de solo lectura o programados que deban
ver el clon tal como está.

`setup_script` se ejecuta solo después de un clon nuevo, dentro del clon, nunca en un
worktree. Un código de salida distinto de cero detiene la tarea. `run --dry-run` nunca
clona ni ejecuta el setup.

## Planificación y estado { #scheduling-and-state }

En cada consulta, Curupira pide al trigger de cada automatización hasta `batch_size`
elementos. Los campos de cada elemento se convierten en un hash que forma la identidad de
la tarea:

- Cada tarea se despacha como máximo una vez por proceso, termine con éxito o con fallo.
- Nada se guarda cuando una tarea termina: tras un reinicio, un elemento que siga coincidiendo
  con los filtros se ejecuta de nuevo. Filtra por un estado que el agente cambia (labels,
  elementos cerrados, pull requests vinculados) para dejar fuera los elementos terminados.
- El mismo elemento con un campo cambiado (un título nuevo, un nuevo commit de head) es una
  identidad nueva, así que puede ejecutarse otra vez en el mismo proceso.
- Una tarea fallida o interrumpida reanuda su sesión del agente cuando se despacha de nuevo.

Filtros como `linked_pull_request = false` deciden qué devuelve el trigger de GitHub;
consulta [Deduplicación](github.md#deduplication) para ver cómo los triggers de GitHub
mantienen estable su salida. Las automatizaciones cron producen una ocurrencia cuando vence
el cronograma y nunca se ejecutan dos veces al mismo tiempo.

Solo un proceso `run` o `tui` despacha a la vez; mantiene `~/.curupira/dispatch.lock`. Una
base de datos de estado incompatible es un error y nunca se elimina automáticamente.
