---
render_macros: false
---

# Referência de campos do prompt

Estes são os nomes que você pode usar em um prompt, seja como `${name}` ou como `{{ name }}` (veja
[Escrevendo prompts](prompts.md)). Execute `curupira validate` para verificar se os nomes que você usa existem.

Os tipos são o que você vê no Jinja: texto, números, booleanos (`true`/`false`) e listas. Com `${name}`
uma lista é inserida como JSON, por exemplo `["bug","security"]`.

## Toda automação

| Campo | Tipo | Significado |
| --- | --- | --- |
| `repo` | texto | O repositório do GitHub `owner/name` (aquele ao qual o item pertence). Em cron, a identidade de `repository` |
| `repository` | texto | O alias do checkout de `[repositories.<alias>]` |
| `automation_id` | texto | O nome da automação, `[automations.<name>]` |
| `automation` | texto | Igual a `automation_id` |
| `task_type` | texto | O trigger, por exemplo `plugins-py/github-issues` ou `cron` |
| `task_number` | texto | O id do item. Em cron, o horário agendado como timestamp Unix |
| `task_title` | texto | O título do item (o nome da automação em cron) |
| `task_body` | texto | O corpo do item, quando o trigger tem um |
| `task_url` | texto | A URL do item (`cron://<name>` em cron) |

## Issues (`github-issues`)

| Campo | Tipo | Significado |
| --- | --- | --- |
| `issue_number` | número | Número da issue |
| `issue_title` | texto | Título |
| `issue_body` | texto | Descrição (vazia se não houver) |
| `issue_url` | texto | URL web |
| `issue_state` | texto | `OPEN` ou `CLOSED` |
| `issue_state_reason` | texto | `COMPLETED`, `NOT_PLANNED`, `REOPENED` ou vazio |
| `issue_author` | texto | Login do autor |
| `issue_labels` | lista | Nomes das labels |
| `issue_assignees` | lista | Logins dos responsáveis |
| `issue_milestone` | texto | Título do milestone, ou vazio |
| `issue_created_at`, `issue_updated_at` | texto | Timestamps ISO, por exemplo `2026-10-01T12:00:00Z` |
| `issue_linked_pull_requests` | lista | URLs dos pull requests que vão fechar a issue |
| `issue_comment_count` | número | Número total de comentários |
| `issue_comments` | texto (JSON) | Os 10 comentários mais recentes. Use `issue_comments \| fromjson` para percorrer `author` e `body` |

## Pull requests (`github-pull-requests`)

| Campo | Tipo | Significado |
| --- | --- | --- |
| `pull_request_number` | número | Número do pull request |
| `pull_request_title`, `pull_request_body`, `pull_request_url` | texto | Título, descrição, URL web |
| `pull_request_author` | texto | Login do autor, por exemplo `app/dependabot` |
| `pull_request_labels` | lista | Nomes das labels |
| `pull_request_assignees` | lista | Logins dos responsáveis |
| `pull_request_requested_reviewers` | lista | Logins ou nomes de times solicitados para revisar |
| `pull_request_milestone` | texto | Título do milestone, ou vazio |
| `pull_request_created_at`, `pull_request_updated_at` | texto | Timestamps ISO |
| `pull_request_head_ref`, `pull_request_base_ref` | texto | Nomes das branches de origem e de destino |
| `pull_request_head_sha` | texto | Id do commit do head |
| `pull_request_is_draft` | booleano | Pull request em rascunho |
| `pull_request_mergeable` | texto | `MERGEABLE`, `CONFLICTING` ou `UNKNOWN` |
| `pull_request_merge_state_status` | texto | `CLEAN`, `BLOCKED`, `BEHIND`, `DIRTY`, `DRAFT`, `HAS_HOOKS`, `UNSTABLE`, `UNKNOWN` |
| `pull_request_review_decision` | texto | `APPROVED`, `CHANGES_REQUESTED`, `REVIEW_REQUIRED` ou vazio quando nenhuma revisão é exigida |
| `pull_request_ci_status` | texto | Estado dos checks no commit do head: `SUCCESS`, `FAILURE`, `PENDING`, `ERROR`, `EXPECTED` ou vazio quando nenhum rodou |
| `pull_request_changed_files`, `pull_request_additions`, `pull_request_deletions` | número | Tamanho da mudança |
| `pull_request_closing_issues` | lista | URLs das issues que o pull request fecha |
| `pull_request_comment_count` | número | Número total de comentários |
| `pull_request_comments` | texto (JSON) | Os 10 comentários mais recentes, como em `issue_comments` |

## Itens de projeto (`github-project-items`) { #project-items }

Issues e pull requests compartilham os nomes `item_*`, então um único prompt funciona para ambos.

| Campo | Tipo | Significado |
| --- | --- | --- |
| `item_type` | texto | `issue` ou `pull_request` |
| `item_number`, `item_title`, `item_body`, `item_url`, `item_state` | texto ou número | Mesmo significado que para issues |
| `item_author` | texto | Login do autor |
| `item_labels`, `item_assignees` | lista | Nomes das labels e logins dos responsáveis |
| `item_milestone` | texto | Título do milestone, ou vazio |
| `item_created_at`, `item_updated_at` | texto | Timestamps ISO |
| `item_comment_count`, `item_comments` | número, texto (JSON) | Como em issues |
| `project_title`, `project_url` | texto | O board |
| `project_column` | texto | A coluna (valor de `status_field`) em que o item foi encontrado |
| `project_fields` | texto (JSON) | Todos os valores de campos do card, por exemplo `{"Status": "Ready", "Priority": "P1"}`. Use `project_fields \| fromjson` |
| `pull_request_head_ref`, `pull_request_base_ref`, `pull_request_head_sha` | texto | Apenas para pull requests, vazio caso contrário |
| `pull_request_is_draft` | booleano | Só faz sentido para pull requests |
| `pull_request_review_decision`, `pull_request_ci_status` | texto | Apenas para pull requests, vazio caso contrário |

## Valores opcionais

Um campo que não tem valor para o item é **texto vazio** (por exemplo, o milestone de uma issue
que não tem um), então `{{ issue_milestone or "none" }}` funciona. Um campo que não se aplica ao item de
forma alguma (por exemplo, `pull_request_head_ref` para uma issue em um projeto) também fica vazio.
