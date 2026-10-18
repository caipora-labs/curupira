# Configuración

## Referencia generada del modelo

La referencia del modelo que aparece a continuación se genera a partir de los modelos públicos de Pydantic. Los tipos de los campos,
los valores predeterminados y las restricciones provienen directamente de los modelos de origen; actualiza esos modelos en lugar de
mantener aquí una tabla de campos paralela.

### Ajustes de ejecución

::: curupira.models.configuration.ExecutionSettings
    options:
      members:
        - max_active_tasks
        - max_pending_tasks
        - workspace_dir
        - state_db_path
        - otlp_endpoint
        - log_level
        - task_timeout_minutes
        - max_output_bytes
        - polling

::: curupira.models.configuration.PollingSettings
    options:
      show_root_heading: true

### Repositorios, agentes y automatizaciones

::: curupira.models.configuration.RepositoryConfiguration

::: curupira.models.configuration.AgentDefaults

::: curupira.models.configuration.AgentsSettings

::: curupira.models.configuration.AssistantSettings

::: curupira.models.configuration.IssueAutomationConfiguration

::: curupira.models.configuration.PullRequestAutomationConfiguration

::: curupira.models.configuration.CronAutomationConfiguration

### Perfiles de CLI

::: curupira.models.profiles.OpenCodeCliProfile

::: curupira.models.profiles.CodexCliProfile

::: curupira.models.profiles.ClaudeCodeCliProfile

::: curupira.models.profiles.CursorCliProfile

El perfil de GitHub Copilot CLI está documentado en su [página de proveedor](providers/copilot.md#configuration-reference).

Un único archivo TOML separa los límites de ejecución, los repositorios Git, los perfiles de agentes de código y las
automatizaciones. Una automatización vigila issues, pull requests, tarjetas o un cronograma cron, y
apunta a un alias de repositorio para el checkout.

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
cron_poll_interval_seconds = 1

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

Guarda esto como `~/.curupira/settings.toml`. Las claves bajo `repositories`, `profiles`,
`plugins` y `automations` son identificadores que tú eliges; `repository` conecta una
automatización con un alias de checkout, `profile` la conecta con un perfil de agente de código, y
`[plugins.<alias>]` registra un lanzador de triggers para que las automatizaciones puedan usar
`<alias>/<local-trigger>` (por ejemplo `plugins-py/github-issues`).

El `provider` de cada perfil selecciona un agente de código **integrado**: `claude`, `codex`, `copilot`,
`cursor`, `gemini`, `kilo`, `opencode`, `pi` o `qwen`. Los agentes de código forman parte de la CLI
de Rust (no son extensiones de proceso). `curu plugins list` muestra esos proveedores como
`agent:<name>` con origen `built-in`, junto con las extensiones de triggers.

## Asistente { #assistant }

`[assistant]` es opcional. Registra qué proveedor de agente de código integrado debe ejecutar
el asistente de configuración interactivo y qué modelo debe usar esa CLI:

- `agent`: el nombre de un proveedor integrado (los mismos identificadores que se usan en los valores
  `provider` de los perfiles). Déjalo sin definir hasta que elijas uno.
- `model`: un id de modelo concreto, u omítelo para preferir la selección automática nativa
  del proveedor cuando el adaptador documente una (`auto` para Cursor, Gemini CLI y GitHub
  Copilot CLI). El literal `auto` se rechaza para los proveedores que no tienen esa capacidad.

Los archivos TOML existentes sin `[assistant]` conservan los valores predeterminados sin definir.

Actualmente `curu tui` ejecuta el despacho continuo con líneas de estado; un panel completo de asistente
integrado es trabajo pendiente. Las recetas de lanzamiento interactivo de cada proveedor integrado ya están
implementadas en el núcleo de Rust para esa futura superficie.

## Plugins

`[plugins.<alias>]` registra un trigger bajo un alias de configuración y declara cómo lanzarlo.
`uvx` y `npx` son lanzadores independientes; los `args` se pasan a esa herramienta como argv
(nunca como una cadena de shell). El host descubre los tipos de trigger lanzando el proceso y
llamando a `describe`, y luego aplica un filtro opcional `tools`:

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

- `type` (obligatorio): `uvx` o `npx`.
- `args` (obligatorio, no vacío): argumentos que van después del binario del lanzador. Los plugins
  oficiales de Python exponen un script de consola `curupira-plugins`, así que los usuarios finales ejecutan
  `uvx --from curupira-plugins curupira-plugins` (sin `python -m`). Los plugins de Node publican
  un paquete npm cuyo `bin` habla el protocolo (normalmente construido con
  [`@caipora/curupira-sdk`](extensions.md#javascript-extension));
  fija la versión en `args` (por ejemplo `@acme/curupira-ext@1.2.3`). `npx` debe estar en
  el `PATH` (instala [Node.js](https://nodejs.org/)).
- `tools` (opcional): lista de globs que selecciona qué nombres de triggers locales se exponen. Vacía u
  omitida, conserva todos los triggers de `describe`. Los patrones positivos (`github-*`, `*`) son
  inclusiones; los patrones que empiezan con `!` (`!github-project-*`) son exclusiones. Un nombre debe coincidir con una
  inclusión cuando hay inclusiones definidas, y no debe coincidir con ninguna exclusión.

Después, las automatizaciones definen `trigger_type = "<alias>/<local-trigger>"`. Los nombres de triggers locales son
nombres en kebab-case declarados por la extensión (por ejemplo `github-issues`). La distribución oficial
`curupira-plugins` normalmente se registra como `plugins-py` con `type = "uvx"`.

## Repositorios

`[repositories.<alias>]` es el dueño de los ajustes de checkout de Git compartidos por una o más automatizaciones:

- `remote` (obligatorio): URL completa de Git que usa `git clone` (HTTPS, SSH o `user@host:path`).
- `path` (opcional): checkout existente o destino alternativo del clon.
- `setup_script` (opcional): ejecutable relativo al repositorio que se corre solo después de un clon nuevo.

El descubrimiento en el forge es independiente de la URL del checkout. Un patrón habitual es un `remote`
en un host distinto de GitHub con issues públicos de GitHub: define `repositories.api.remote` con
esa URL de Git y define el `repo` de GitHub de la automatización como `owner/name`.

## Automatizaciones

`trigger_type` selecciona la fuente:

- `plugins-py/github-issues` descubre issues de GitHub mediante la búsqueda de GraphQL usando filtros tipados
  (`labels`, `exclude_labels`, `assignee`, `linked_pull_request`, `sort`, …). Define
  `linked_pull_request = false` para que el descubrimiento compile `-linked:pr` y omita los issues que
  ya tienen un pull request vinculado. Ese filtro es solo de descubrimiento en tiempo de configuración;
  consulta [Planificación y estado](#scheduling-and-state) para ver la revalidación del planificador de las sesiones
  recuperadas.
- `plugins-py/github-pull-requests` descubre pull requests de GitHub de la misma manera, con filtros de PR como
  `draft`, `review`, `ci_status`, además de los post-filtros `mergeable` / `merge_state`.
- `cron` produce ocurrencias a partir de un `schedule` de cinco campos en lugar de consultar un forge.
- Las [extensiones de triggers](extensions.md) instaladas añaden sus propios tipos de trigger;
  `curu plugins list` muestra todos los tipos disponibles.

Cada automatización requiere `repository` (alias) y `prompt`. Los triggers de GitHub también
requieren la identidad `repo` del forge (`owner/name`). Cron requiere `schedule`. El `profile` opcional
selecciona un perfil de CLI. Distintos alias de repositorio no pueden compartir una misma ruta de workspace. Las automatizaciones conservan
el orden del archivo, y la selección de una sola pasada sigue ese orden.

La autenticación de la API de GitHub usa `gh auth token` de una CLI de GitHub ya autenticada.
La autenticación del clon usa las credenciales nativas de Git para el `remote` configurado.

Los placeholders usan la sintaxis `${name}` (también están disponibles condicionales y bucles de Jinja; consulta
[Cómo escribir prompts](prompts.md)). El host siempre proporciona `${repository}` (la
identidad del forge derivada del remote de Git) y `${automation}` (el nombre de la
automatización). Cualquier otro `${key}` proviene del resultado del trigger: el SDK convierte el
objeto devuelto en pares de cadenas, y cada clave se sustituye tal como está escrita,
incluidas las claves que no son identificadores comunes (`${issue-number}`). Un
placeholder sin coincidencia se deja sin cambios (puede ser texto de shell como `${HOME}`);
`validate` solo se queja cuando un `${name}` o `{{ name }}` parece un error tipográfico de una clave real. Los plugins oficiales eligen sus propias claves. Los issues de GitHub
incluyen `issue_number`, `issue_title`, `issue_body` e `issue_url`;
los pull requests incluyen `pull_request_number`, `pull_request_title`,
`pull_request_body`, `pull_request_url`, `pull_request_is_draft`,
`pull_request_head_ref`, `pull_request_base_ref`, `pull_request_head_sha` y
`pull_request_mergeable`, entre los demás campos de ese modelo. Los prompts de cron
solo reciben las dos variables del host (y la forma heredada `$automation`).

## Checkout y preparación

De forma predeterminada, cada tarea usa su propio worktree, creado a partir de la rama predeterminada remota obtenida con fetch.
Define `checkout = "main"` para usar el checkout compartido tal cual; en ese modo Curupira no hace fetch, pull ni
cambia de rama. El `path` del alias del repositorio selecciona el checkout base.
Los clones usan `git clone <remote>`.

`setup_script` vive en el alias del repositorio. Se ejecuta directamente solo después de que un checkout base
se clona desde cero, no para un checkout existente ni dentro de un worktree de tarea. Una salida distinta de cero
impide que el agente arranque y elimina el checkout recién clonado. La validación comprueba la sintaxis de la
ruta pero no exige que el script exista. `run --dry-run` no hace fetch, no clona,
no crea worktrees ni ejecuta la preparación.

## Planificación y estado { #scheduling-and-state }

Cada consulta obtiene hasta `batch_size` elementos (100 por defecto, máximo 1000). Los ciclos de consulta vacíos aumentan la espera
desde `poll_interval_seconds` (30 segundos por defecto) hasta cinco minutos; al descubrir trabajo se reinicia
la espera. Las automatizaciones deduplican de forma independiente.

Los filtros de descubrimiento como `linked_pull_request = false` (`-linked:pr`) solo afectan a lo que
devuelve la búsqueda de GitHub para trabajo nuevo. No protegen las sesiones recuperadas que se guardaron
antes de que un issue obtuviera un PR vinculado. La aplicación del planificador es independiente: antes de admitir una tarea nueva o
una sesión guardada, Curupira obtiene una vez el estado actual del issue o del pull request,
descarta los elementos cerrados o fusionados, rechaza un issue que ya tiene un PR de cierre abierto o vinculado
en Development (mediante `closedByPullRequestsReferences` de GraphQL, incluidas formas en el cuerpo
como `Fixes: #N`), retira su sesión de issue obsoleta y reinicia una sesión de PR cuando el
SHA del head, el indicador de borrador, el título o el cuerpo ya no coinciden con el snapshot guardado. Las sesiones
de pull request recuperadas de una base de datos de estado escrita antes de que se persistiera el SHA del head se reinician una vez
cuando el snapshot actualizado aporta un head. Si GitHub informa más referencias de PR de cierre
que una página de GraphQL, la admisión falla de forma cerrada para ese candidato (sin agente). Un error transitorio de
revalidación aplaza ese candidato, conserva cualquier sesión guardada y no detiene el
planificador.

Las consultas de una sola pasada y las iniciales llaman juntos a todos los feeds de las automatizaciones. Un `DispatchError` de un
feed se registra en el log y ese feed no aporta tareas; los demás feeds siguen devolviendo candidatos.
Luego `run` (una sola pasada) prueba los candidatos en orden y pasa al siguiente cuando la revalidación
descarta uno. `run --watch` / `tui` continuos transmiten los errores de descubrimiento por feed ya registrados
de la misma manera.

Después de una ejecución exitosa del agente (la CLI del agente de código realmente se ejecutó), Curupira guarda
la huella digital de la fuente completada junto con una siguiente acción explícita en `state_db_path`. Un snapshot
completado sin cambios se omite entre ciclos de despacho. Las huellas usan el SHA del head, el indicador de borrador,
el título y el cuerpo, y no la capacidad de fusión, el estado de merge ni las conclusiones de los checks, así que las
transiciones de checks o de conflictos por sí solas no vuelven a admitir trabajo. Un head, un indicador de borrador, un título o un cuerpo
que cambien pueden admitirse de nuevo. Si la propia verificación de la finalización falla, Curupira borra cualquier registro
de completado de ese elemento para que el siguiente ciclo reintente la verificación en lugar de omitirlo para siempre.
Los snapshots omitidos por obsoletos antes de que el agente arranque no se registran como completados.

Los vaciados finitos con `run --size N` admiten como máximo `N` tareas tras la revalidación. Las sesiones recuperadas
cuentan para `N`; los candidatos descartados durante la revalidación no.

`max_active_tasks` limita los agentes concurrentes (ranuras de trabajo). Cuando una tarea termina, su ranura se
rellena de inmediato con la siguiente consulta. Las tareas que comparten un checkout base serializan su clon
y la preparación de su worktree, pero sus agentes se ejecutan en paralelo. Una tarea que falla no se reintenta dentro
de la misma invocación de `run`; la siguiente invocación la recoge de nuevo.
Las automatizaciones de cron combinan los disparos atrasados en una sola ocurrencia pendiente y nunca se ejecutan
concurrentemente consigo mismas. `schedule` usa cinco campos de cron; `timezone` es una zona IANA (UTC por defecto),
y `start_date`/`end_date` opcionales definen una ventana inclusiva. Sin `start_date`, la
ventana empieza cuando la automatización se registra por primera vez. `task_timeout_minutes` (20 por defecto) es
el plazo para una ejecución del agente de código y su script de preparación opcional.

El estado se guarda en `state_db_path` (por defecto `~/.curupira/state.sqlite3`), el lock de despacho
en `~/.curupira/dispatch.lock` y los logs en `~/.curupira/logs`. Una base de datos incompatible
produce un error en lugar de borrarse automáticamente. Solo un proceso `run` o `tui` puede despachar
a la vez.

## Telemetría

Define `settings.otlp_endpoint` con un endpoint de trazas OTLP/HTTP (por ejemplo,
`http://localhost:4318/v1/traces`) para exportar un span por cada tarea despachada. Si se omite, no se
exporta telemetría.
