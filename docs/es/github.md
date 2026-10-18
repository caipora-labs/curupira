# Issues y pull requests de GitHub

Curupira descubre issues y pull requests de GitHub con filtros tipados en TOML, los compila
en consultas de [GitHub Search](https://docs.github.com/en/search-github/searching-on-github/searching-issues-and-pull-requests)
y ejecuta esas consultas mediante la API GraphQL. La autenticación es un bearer token
obtenido con `gh auth token`. Curupira no crea, edita, cierra ni comenta issues o pull
requests.

Cada coincidencia se convierte en una **tarea**: un elemento tipado (campos de issue o de
pull request), una identidad usada para la deduplicación, un prompt renderizado para una
CLI de agente de código y un checkout o worktree local de Git donde se ejecuta ese agente.

| Tipo de trigger | Qué descubre |
| --- | --- |
| `plugins-py/github-issues` | Issues de un `owner/repository` |
| `plugins-py/github-pull-requests` | Pull requests de un `owner/repository` |
| `plugins-py/github-project-items` | Issues y pull requests en una columna de un tablero de GitHub Projects. Consulta [GitHub Projects](github-projects.md) |

## Requisitos previos { #prerequisites }

1. Instala la [CLI de GitHub](https://cli.github.com/) (`gh`).
2. Autentícate una vez:

   ```sh
   gh auth login
   ```

3. Confirma que `gh` tiene un token (Curupira lo lee con el mismo comando):

   ```sh
   gh auth token
   ```

Curupira no almacena credenciales de GitHub. Ejecuta `gh auth token` (con caché de cinco
minutos) y envía ese bearer token a `https://api.github.com/graphql`. Las operaciones de
clon y worktree usan `git` nativo y tus credenciales de Git habituales para el `remote`
del repositorio, no `gh repo clone`.

### Alcances del token { #token-scopes }

Usa un token con el alcance `repo` para repositorios privados, o `public_repo` si solo
necesitas repositorios públicos. Revisa `gh auth status` para ver los alcances de tu
sesión actual. Curupira solo lee resultados de Search; el agente de código que lanza puede
hacer más, según su perfil. Consulta
[la guía de autenticación de GraphQL de GitHub](https://docs.github.com/en/graphql/guides/forming-calls-with-graphql#authenticating-with-graphql)
para saber cómo se relacionan los datos solicitados con los alcances.

## Automatización mínima de issues { #minimal-issue-automation }

En una automatización, `repo` es el `owner/name` de GitHub que Curupira busca.
`repository` es el alias de un checkout `[repositories.<alias>]` donde se ejecuta el
agente. Pueden ser distintos.

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "opencode-default"
timezone = "UTC"

[agents.profiles.opencode-default]
provider = "opencode"

[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
linked_pull_request = false
prompt = "Resolve issue ${issue_number}: ${issue_title}\n\n${issue_body}"
```

Valida sin contactar con GitHub:

```sh
curupira --config path/to/settings.toml validate
```

## Automatización mínima de pull requests { #minimal-pull-request-automation }

`repo` y `repository` significan lo mismo que en [Automatización mínima de issues](#minimal-issue-automation).

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "opencode-default"
timezone = "UTC"

[agents.profiles.opencode-default]
provider = "opencode"

[automations.review-pull-requests]
trigger_type = "plugins-py/github-pull-requests"
repository = "api"
repo = "acme/api"
labels = ["review-needed"]
draft = false
prompt = """
Review pull request ${pull_request_number}: ${pull_request_title}

${pull_request_body}

Branch: ${pull_request_head_ref} -> ${pull_request_base_ref}
"""
```

## Automatización de pull requests de Dependabot { #dependabot-pull-request-automation }

Filtra por un solo autor con `author = "app/dependabot"` y exige `mergeable = true` para
que los pull requests con conflictos se dejen en paz. El prompt siguiente solo usa
placeholders listados arriba, y `${repo}` lleva el `owner/name` que se usa en cada comando
`gh`. El perfil del agente necesita `auto_approve = true` para que las escrituras de `gh`
sin supervisión (push, `gh pr merge`) no se detengan a pedir aprobación.

```toml
[automations.merge-dependabot-pull-requests]
trigger_type = "plugins-py/github-pull-requests"
repository = "curupira"
repo = "caipora-labs/curupira"
author = "app/dependabot"
state = "open"
draft = false
mergeable = true
sort = "created-asc"
prompt = """
Analyze Dependabot pull request #${pull_request_number} (${pull_request_title}) in ${repo}.
Fix what the update breaks, wait for the checks, then squash-merge it with
`gh pr merge ${pull_request_number} --repo ${repo} --squash`.
"""
```

Ejecútalo hasta que se hayan gestionado los pull requests abiertos de Dependabot:

```sh
curupira --config path/to/settings.toml run --watch --size 12
```

## Primera ejecución { #first-run }

1. Instala y autentica la CLI del agente de código indicada en tu perfil (`opencode` en
   los fragmentos anteriores). Las opciones nativas de cada proveedor y las notas de
   configuración están en las páginas de [Proveedores y agentes](providers.md).
2. Previsualiza una tarea coincidente sin clonar ni iniciar un agente:

   ```sh
   curupira --config path/to/settings.toml run --dry-run
   ```

3. Procesa una vez las tareas disponibles en ese momento, o consulta de forma continua:

   ```sh
   curupira --config path/to/settings.toml run
   curupira --config path/to/settings.toml run --watch
   ```

`--dry-run` no se puede combinar con `--watch` ni con `--size`. `validate` comprueba la
estructura del TOML y los placeholders del prompt sin llamar a GitHub; `run` y
`run --watch` necesitan `gh` y la CLI del agente elegido instaladas y autenticadas.

## Campos de configuración { #configuration-fields }

Los modelos rechazan las claves desconocidas.

### Campos compartidos de la automatización { #shared-automation-fields }

| Campo | Valor por defecto | Notas |
| --- | --- | --- |
| `trigger_type` | ver notas | Defínelo explícitamente como `"plugins-py/github-issues"` o `"plugins-py/github-pull-requests"`. Si se omite al interpretar el TOML, Curupira elige `"plugins-py/github-issues"` solo cuando la tabla no tiene `schedule`; una clave `schedule` hace que el valor por defecto sea `"cron"` |
| `repository` | *(obligatorio)* | Alias de una entrada `[repositories.<alias>]` |
| `checkout` | `"worktree"` | `"worktree"` o `"main"` (checkout compartido, no un nombre de rama) |
| `prompt` | *(obligatorio)* | `string.Template` no vacío con `${placeholders}` |
| `profile` | `None` | Perfil de CLI con nombre; si no, `agents.defaults.profile`, que por defecto es `"opencode"`. Consulta [Proveedores y agentes](providers.md) para ver las opciones de perfil |

### Filtros compartidos de GitHub { #shared-github-filters }

Se compilan en la consulta de Search.

| Campo | Valor por defecto | Calificador de Search / comportamiento |
| --- | --- | --- |
| `repo` | *(obligatorio)* | `repo:owner/name` (formato `owner/repository`) |
| `state` | `"open"` | `"open"` → `is:open`; `"closed"` → `is:closed`; `"all"` → ninguno. En los pull requests, `is:closed` incluye los PR con merge |
| `labels` | `()` | Un label o una lista. Cada valor → `label:…` (AND: deben estar presentes todos los labels) |
| `exclude_labels` | `()` | Un label o una lista. Cada valor → `-label:…` |
| `assignee` | `None` | Login, `@me`, `none` → `no:assignee`, o `any` → `assignee:*` |
| `author` | `None` | `author:…` |
| `milestone` | `None` | `milestone:…` |
| `project` | `None` | `project:<value>`, por ejemplo `acme/5` |
| `sort` | `"created-asc"` | Se añade como `sort:…`. Valores permitidos: `created-asc`, `created-desc`, `updated-asc`, `updated-desc`, `comments-asc`, `comments-desc` |

El calificador `project` solo restringe a qué proyecto pertenece un elemento. Para elegir
elementos por columna del tablero, usa [`github-project-items`](github-projects.md). Los
valores con espacios en blanco o con `"`, `:`, `,` se entrecomillan en la consulta
compilada.

### Campos solo para issues { #issue-only-fields }

| Campo | Valor por defecto | Comportamiento |
| --- | --- | --- |
| `linked_pull_request` | `None` | `true` → `linked:pr`; `false` → `-linked:pr`; omítelo para no filtrar |

### Campos solo para pull requests { #pull-request-only-fields }

| Campo | Valor por defecto | Comportamiento |
| --- | --- | --- |
| `draft` | `None` | `true` → `draft:true`; `false` → `draft:false` |
| `base` | `None` | `base:…` |
| `head` | `None` | `head:…` |
| `review` | `None` | `review:…` — `none`, `required`, `approved` o `changes_requested` |
| `ci_status` | `None` | `status:…` — `success`, `failure` o `pending` |
| `linked_issue` | `None` | `true` → `linked:issue`; `false` → `-linked:issue` |
| `mergeable` | `None` | Posfiltro de GraphQL: `true` conserva `MERGEABLE`; `false` conserva `CONFLICTING` |
| `merge_state` | `()` | Posfiltro de GraphQL: conserva solo los valores de `mergeStateStatus` listados (`BEHIND`, `BLOCKED`, `CLEAN`, `DIRTY`, `DRAFT`, `HAS_HOOKS`, `UNKNOWN`, `UNSTABLE`) |

`mergeable` y `merge_state` se aplican después de que Search devuelve resultados; no son
calificadores de Search.

### Ajustes de polling relacionados { #related-polling-settings }

Bajo `[settings.polling]`:

| Campo | Valor por defecto |
| --- | --- |
| `poll_interval_seconds` | `30.0` |
| `batch_size` | `100` (máximo 1000) |
| `cron_poll_interval_seconds` | `1.0` |

## Cómo se seleccionan los issues y pull requests { #how-issues-and-pull-requests-are-selected }

Cada consulta que se construye empieza siempre con `repo:<repo>` y con `is:issue` o
`is:pr`, y luego añade los filtros anteriores y `sort:<sort>`. Ejemplo para la
automatización mínima de issues:

```text
repo:acme/api is:issue is:open label:agent-ready -linked:pr sort:created-asc
```

El descubrimiento usa GraphQL Search (el tipo de búsqueda `ISSUE` cubre tanto issues como
pull requests). No existe un campo `query` de formato libre: los filtros son solo TOML
tipado.

### Deduplicación { #deduplication }

Una tarea se identifica por `[automation_id, repo, task_type, id]`. Curupira mantiene dos
registros:

- **Las tareas completadas se recuerdan entre reinicios.** Cuando el agente termina con
  éxito, la tarea se guarda en la base de datos de estado (`state_db_path`) y nunca
  vuelve a ejecutarse para esa automatización, aunque el elemento siga coincidiendo con
  tus filtros.
- **Las tareas fallidas se reintentan.** Una tarea cuya ejecución del agente falló no se
  guarda como completada. Se omite durante el resto del proceso actual y se intenta de
  nuevo tras un reinicio.

La deduplicación es por automatización, así que dos automatizaciones pueden procesar el
mismo issue o pull request con prompts distintos. `run --dry-run` previsualiza sin
registrar nada.

!!! tip "Ejecutar un elemento otra vez"
    Para ejecutar de nuevo un elemento completado, usa un nombre de automatización
    distinto (una automatización nueva tiene su propio historial) o elimina la fila de la
    base de datos de estado. Cambiar solo los filtros no vuelve a hacer elegible un
    elemento completado.

Cuando un ciclo completo no encuentra nada (o el descubrimiento falla), el feed espera
`poll_interval_seconds` y luego duplica la espera en ciclos vacíos consecutivos hasta
cinco minutos (`300` segundos). Cualquier descubrimiento exitoso restablece el intervalo.

## Qué recibe el prompt del agente { #what-the-agent-prompt-receives }

El prompt puede usar `${field}` o sintaxis Jinja; consulta [Escribir prompts](prompts.md).
Todos los campos de issues y pull requests (título, cuerpo, labels, asignados,
comentarios, estado de revisión, estado de CI y más) están listados en la
[Referencia de campos del prompt](prompt-fields.md).

## Seguridad: el texto de issues y pull requests no es confiable { #security }

Los títulos, cuerpos y comentarios (`${issue_title}`, `${issue_body}`, `${issue_comments}`,
`${pull_request_title}`, `${pull_request_body}`, `${pull_request_comments}`, `${item_body}`,
`${item_comments}`) vienen de cualquier persona que pueda abrir un issue o pull request y
se colocan en el prompt del agente de código, así que un autor hostil puede intentar
dirigir al agente (prompt injection). El agente puede ejecutar acciones destructivas en el
checkout donde trabaja, por lo que el riesgo depende de lo que permitas en el perfil del
agente. Restringe lo que llega al agente con `labels` (aplicados solo por personas de
confianza), `author` o `assignee`, y revisa qué puede ejecutar tu perfil de agente.

## Checkout y worktrees { #checkout-and-worktrees }

Los triggers de GitHub usan el control de versiones nativo de Git por defecto.

1. Curupira clona `repositories.<alias>.remote` en `workspace_dir/<alias>` (o en el
   `path` del alias) la primera vez que se usa.
2. Con `checkout = "worktree"` (por defecto), hace fetch de `origin`, resuelve la rama
   predeterminada remota y añade un worktree en
   `<checkout>.worktrees/<automation_id>/<task_type>-<sha256(task_id)>` sobre la rama
   `curupira/<automation_id>/<task_type>-<sha256(task_id)>`. La rama no se sube con push.
3. Con `checkout = "main"`, el agente se ejecuta en el checkout compartido tal como está:
   sin fetch, pull ni cambio de rama.
4. Cuando el agente termina, Curupira elimina el worktree y borra la rama local (los
   fallos de limpieza se registran en el log, no son fatales).

El `setup_script` opcional del alias del repositorio se ejecuta solo después de un clon
nuevo del checkout base, no dentro del worktree.

### Aislamiento del agente { #agent-isolation }

El proceso del agente se ejecuta con su directorio de trabajo y `PWD` apuntando al
worktree, y sin las variables `GIT_DIR`, `GIT_WORK_TREE` y `GIT_INDEX_FILE` que harían
que Git apunte a otro repositorio. Una automatización nunca cambia tu propio checkout.
Para OpenCode, Curupira también pasa `--dir <worktree>` y asigna a cada tarea su propio
`OPENCODE_DB` en `<worktree>.opencode.db`, de modo que las sesiones y entradas de
proyecto de OpenCode permanezcan con esa tarea. Otro estado global del agente, como la
configuración global y las credenciales de OpenCode, sigue compartido.

## Errores comunes { #common-errors }

| Síntoma | Causa probable | Solución |
| --- | --- | --- |
| `Required executable not found: gh` | La CLI de GitHub no está en el `PATH` | Instala `gh` y vuelve a intentarlo |
| `gh exited with status …` / token vacío | No hay sesión iniciada o el token no está disponible | Ejecuta `gh auth login` y luego `gh auth token` |
| Errores GraphQL / HTTP 401 o de alcances | El token no tiene acceso al repositorio o a Search | Vuelve a ejecutar `gh auth login` para que el token incluya `repo`, o usa un PAT clásico con los alcances que exige [la guía de GraphQL de GitHub](https://docs.github.com/en/graphql/guides/forming-calls-with-graphql#authenticating-with-graphql) |
| No hay tareas programadas | Los filtros no coinciden con nada | Amplía labels/state, quita los filtros `linked_*` / `draft` o confirma que `repo` es correcto; los ciclos vacíos no son un error |
| `GitHub GraphQL temporarily failed with status 429` (o similar) | Límite de tasa o fallo transitorio de la API | Curupira reintenta los errores transitorios unas cuantas veces; espera o reduce la frecuencia de polling / `batch_size` |
| Advertencias de descubrimiento en `run --watch` | Un fallo de GraphQL o de la CLI se trata como ciclo vacío | Revisa los logs en busca de `Discovery failed for …`; corrige la autenticación o la red y espera al siguiente poll |

`curupira validate` comprueba la estructura del TOML y los placeholders del prompt sin
llamar a GitHub. `curupira run` y `curupira run --watch` necesitan `gh` instalado y
autenticado.
