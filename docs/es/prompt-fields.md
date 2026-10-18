---
render_macros: false
---

# Referencia de campos del prompt

Estos son los nombres que puedes usar en un prompt, ya sea como `${name}` o como `{{ name }}` (consulta
[Cómo escribir prompts](prompts.md)). Ejecuta `curupira validate` para comprobar que los nombres que usas existen.

Todo valor es texto (consulta [Todo valor es texto](prompts.md#values-are-text)). Los números, los booleanos
(`true`/`false`) y las listas aparecen en la columna *Tipo* por lo que significan; una lista es texto JSON,
por ejemplo `["bug","security"]`, que abres con `| fromjson`.

## Toda automatización

| Campo | Tipo | Significado |
| --- | --- | --- |
| `repository` | texto | El repositorio de GitHub `owner/name` del checkout de la automatización (a partir del remote de Git) |
| `automation` | texto | El nombre de la automatización, `[automations.<name>]` |

Los prompts de cron reciben solo estos dos.

## Issues (`github-issues`)

| Campo | Tipo | Significado |
| --- | --- | --- |
| `repo` | texto | El repositorio `owner/name` al que pertenece la issue |
| `id`, `title`, `url` | texto | Número, título y URL web de la issue (igual que los campos `issue_*`) |
| `issue_number` | número | Número de la issue |
| `issue_title` | texto | Título |
| `issue_body` | texto | Descripción (vacía si no hay) |
| `issue_url` | texto | URL web |
| `issue_state` | texto | `OPEN` o `CLOSED` |
| `issue_state_reason` | texto | `COMPLETED`, `NOT_PLANNED`, `REOPENED` o vacío |
| `issue_author` | texto | Login del autor |
| `issue_labels` | lista | Nombres de los labels |
| `issue_assignees` | lista | Logins de las personas asignadas |
| `issue_milestone` | texto | Título del hito, o vacío |
| `issue_created_at` | texto | Timestamp ISO, por ejemplo `2026-10-01T12:00:00Z` |

## Pull requests (`github-pull-requests`)

| Campo | Tipo | Significado |
| --- | --- | --- |
| `repo` | texto | El repositorio `owner/name` al que pertenece el pull request |
| `id`, `title`, `url` | texto | Número, título y URL web del pull request (igual que los campos `pull_request_*`) |
| `pull_request_number` | número | Número del pull request |
| `pull_request_title`, `pull_request_body`, `pull_request_url` | texto | Título, descripción, URL web |
| `pull_request_author` | texto | Login del autor, por ejemplo `app/dependabot` |
| `pull_request_labels` | lista | Nombres de los labels |
| `pull_request_assignees` | lista | Logins de las personas asignadas |
| `pull_request_milestone` | texto | Título del hito, o vacío |
| `pull_request_created_at` | texto | Timestamp ISO |
| `pull_request_head_ref`, `pull_request_base_ref` | texto | Nombres de la rama de origen y de la rama de destino |
| `pull_request_head_sha` | texto | Id del commit del head |
| `pull_request_is_draft` | booleano | Pull request en borrador |
| `pull_request_mergeable` | texto | `MERGEABLE`, `CONFLICTING` o `UNKNOWN` |
| `pull_request_merge_state_status` | texto | `CLEAN`, `BLOCKED`, `BEHIND`, `DIRTY`, `DRAFT`, `HAS_HOOKS`, `UNSTABLE`, `UNKNOWN` |
| `pull_request_changed_files`, `pull_request_additions`, `pull_request_deletions` | número | Tamaño del cambio |
| `pull_request_closing_issues` | lista | URLs de las issues que cierra el pull request |

## Elementos del proyecto (`github-project-items`) { #project-items }

Las issues y los pull requests comparten los nombres `item_*`, así que un mismo prompt sirve para ambos.

| Campo | Tipo | Significado |
| --- | --- | --- |
| `repo` | texto | El repositorio `owner/name` al que pertenece el elemento |
| `id`, `title`, `url` | texto | `owner/name#number`, el título y la URL web |
| `item_type` | texto | `issue` o `pull_request` |
| `item_number`, `item_title`, `item_body`, `item_url`, `item_state` | texto o número | Mismo significado que para las issues |
| `item_author` | texto | Login del autor |
| `item_labels`, `item_assignees` | lista | Nombres de los labels y logins de las personas asignadas |
| `item_milestone` | texto | Título del hito, o vacío |
| `item_created_at` | texto | Timestamp ISO |
| `project_title`, `project_url` | texto | El tablero |
| `project_column` | texto | La columna (valor de `status_field`) en la que se encontró el elemento |
| `project_fields` | texto (JSON) | Todos los valores de los campos de la tarjeta, por ejemplo `{"Status": "Ready", "Priority": "P1"}`. Usa `project_fields \| fromjson` |
| `pull_request_head_ref`, `pull_request_base_ref`, `pull_request_head_sha` | texto | Solo para pull requests, vacío en los demás casos |
| `pull_request_is_draft` | booleano | Solo tiene sentido para pull requests |

## Lo que se deja fuera a propósito { #left-out-on-purpose }

Los comentarios, la hora de actualización, el estado de CI y de revisión, los pull requests vinculados y las personas
revisoras solicitadas no son campos. El host calcula un hash de cada campo que devuelve un trigger para obtener la identidad
de la tarea ([Deduplicación](github.md#deduplication)), así que un valor que cambia por sí solo, o porque el
agente trabajó en el elemento, iniciaría de nuevo el mismo issue. Pide al agente que lea lo que necesite,
por ejemplo `gh issue view ${issue_number} --comments` o `gh pr checks ${pull_request_number}`.
El estado de CI y de revisión se puede seguir usando para *seleccionar* pull requests con los filtros `ci_status` y
`review`.

## Valores opcionales

Un campo que no tiene valor para el elemento es **texto vacío** (por ejemplo, el hito de una issue
que no tiene ninguno), así que `{{ issue_milestone or "none" }}` funciona. Un campo que no se aplica en absoluto al elemento (por
ejemplo, `pull_request_head_ref` para una issue en un proyecto) también está vacío.
