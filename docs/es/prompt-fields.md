---
render_macros: false
---

# Referencia de campos del prompt

Estos son los nombres que puedes usar en un prompt, ya sea como `${name}` o como `{{ name }}` (consulta
[Cómo escribir prompts](prompts.md)). Ejecuta `curupira validate` para comprobar que los nombres que usas existen.

Los tipos son los que ves en Jinja: texto, números, booleanos (`true`/`false`) y listas. Con `${name}`
una lista se inserta como JSON, por ejemplo `["bug","security"]`.

## Toda automatización

| Campo | Tipo | Significado |
| --- | --- | --- |
| `repo` | texto | El repositorio de GitHub `owner/name` (al que pertenece el elemento). Para cron, la identidad de `repository` |
| `repository` | texto | El alias del checkout de `[repositories.<alias>]` |
| `automation_id` | texto | El nombre de la automatización, `[automations.<name>]` |
| `automation` | texto | Igual que `automation_id` |
| `task_type` | texto | El trigger, por ejemplo `plugins-py/github-issues` o `cron` |
| `task_number` | texto | El id del elemento. Para cron, la hora programada como timestamp Unix |
| `task_title` | texto | El título del elemento (el nombre de la automatización para cron) |
| `task_body` | texto | El cuerpo del elemento, cuando el trigger tiene uno |
| `task_url` | texto | La URL del elemento (`cron://<name>` para cron) |

## Issues (`github-issues`)

| Campo | Tipo | Significado |
| --- | --- | --- |
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
| `issue_created_at`, `issue_updated_at` | texto | Timestamps ISO, por ejemplo `2026-10-01T12:00:00Z` |
| `issue_linked_pull_requests` | lista | URLs de los pull requests que cerrarán la issue |
| `issue_comment_count` | número | Número total de comentarios |
| `issue_comments` | texto (JSON) | Los últimos 10 comentarios. Usa `issue_comments \| fromjson` para recorrer `author` y `body` |

## Pull requests (`github-pull-requests`)

| Campo | Tipo | Significado |
| --- | --- | --- |
| `pull_request_number` | número | Número del pull request |
| `pull_request_title`, `pull_request_body`, `pull_request_url` | texto | Título, descripción, URL web |
| `pull_request_author` | texto | Login del autor, por ejemplo `app/dependabot` |
| `pull_request_labels` | lista | Nombres de los labels |
| `pull_request_assignees` | lista | Logins de las personas asignadas |
| `pull_request_requested_reviewers` | lista | Logins o nombres de equipos a los que se pidió revisar |
| `pull_request_milestone` | texto | Título del hito, o vacío |
| `pull_request_created_at`, `pull_request_updated_at` | texto | Timestamps ISO |
| `pull_request_head_ref`, `pull_request_base_ref` | texto | Nombres de la rama de origen y de la rama de destino |
| `pull_request_head_sha` | texto | Id del commit del head |
| `pull_request_is_draft` | booleano | Pull request en borrador |
| `pull_request_mergeable` | texto | `MERGEABLE`, `CONFLICTING` o `UNKNOWN` |
| `pull_request_merge_state_status` | texto | `CLEAN`, `BLOCKED`, `BEHIND`, `DIRTY`, `DRAFT`, `HAS_HOOKS`, `UNSTABLE`, `UNKNOWN` |
| `pull_request_review_decision` | texto | `APPROVED`, `CHANGES_REQUESTED`, `REVIEW_REQUIRED` o vacío cuando no se requiere revisión |
| `pull_request_ci_status` | texto | Estado de los checks del commit head: `SUCCESS`, `FAILURE`, `PENDING`, `ERROR`, `EXPECTED` o vacío si no se ejecutó ninguno |
| `pull_request_changed_files`, `pull_request_additions`, `pull_request_deletions` | número | Tamaño del cambio |
| `pull_request_closing_issues` | lista | URLs de las issues que cierra el pull request |
| `pull_request_comment_count` | número | Número total de comentarios |
| `pull_request_comments` | texto (JSON) | Los últimos 10 comentarios, igual que `issue_comments` |

## Elementos del proyecto (`github-project-items`) { #project-items }

Las issues y los pull requests comparten los nombres `item_*`, así que un mismo prompt sirve para ambos.

| Campo | Tipo | Significado |
| --- | --- | --- |
| `item_type` | texto | `issue` o `pull_request` |
| `item_number`, `item_title`, `item_body`, `item_url`, `item_state` | texto o número | Mismo significado que para las issues |
| `item_author` | texto | Login del autor |
| `item_labels`, `item_assignees` | lista | Nombres de los labels y logins de las personas asignadas |
| `item_milestone` | texto | Título del hito, o vacío |
| `item_created_at`, `item_updated_at` | texto | Timestamps ISO |
| `item_comment_count`, `item_comments` | número, texto (JSON) | Igual que para las issues |
| `project_title`, `project_url` | texto | El tablero |
| `project_column` | texto | La columna (valor de `status_field`) en la que se encontró el elemento |
| `project_fields` | texto (JSON) | Todos los valores de los campos de la tarjeta, por ejemplo `{"Status": "Ready", "Priority": "P1"}`. Usa `project_fields \| fromjson` |
| `pull_request_head_ref`, `pull_request_base_ref`, `pull_request_head_sha` | texto | Solo para pull requests, vacío en los demás casos |
| `pull_request_is_draft` | booleano | Solo tiene sentido para pull requests |
| `pull_request_review_decision`, `pull_request_ci_status` | texto | Solo para pull requests, vacío en los demás casos |

## Valores opcionales

Un campo que no tiene valor para el elemento es **texto vacío** (por ejemplo, el hito de una issue
que no tiene ninguno), así que `{{ issue_milestone or "none" }}` funciona. Un campo que no se aplica en absoluto al elemento (por
ejemplo, `pull_request_head_ref` para una issue en un proyecto) también está vacío.
