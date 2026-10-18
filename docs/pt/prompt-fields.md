---
render_macros: false
---

# Referência de campos do prompt

Estes são os nomes que você pode usar em um prompt, seja como `${name}` ou como `{{ name }}` (veja
[Escrevendo prompts](prompts.md)). Execute `curupira validate` para verificar se os nomes que você usa existem.

Todo valor é texto (veja [Todo valor é texto](prompts.md#values-are-text)). Números, booleanos
(`true`/`false`) e listas aparecem na coluna *Tipo* pelo que significam; uma lista é um texto JSON,
por exemplo `["bug","security"]`, que você abre com `| fromjson`.

## Toda automação

| Campo | Tipo | Significado |
| --- | --- | --- |
| `repository` | texto | O repositório do GitHub `owner/name` do checkout da automação (a partir do remote Git) |
| `automation` | texto | O nome da automação, `[automations.<name>]` |

Os prompts de cron recebem apenas esses dois.

## Issues (`github-issues`)

| Campo | Tipo | Significado |
| --- | --- | --- |
| `repo` | texto | O repositório `owner/name` ao qual a issue pertence |
| `id`, `title`, `url` | texto | Número, título e URL web da issue (igual aos campos `issue_*`) |
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
| `issue_created_at` | texto | Timestamp ISO, por exemplo `2026-10-01T12:00:00Z` |

## Pull requests (`github-pull-requests`)

| Campo | Tipo | Significado |
| --- | --- | --- |
| `repo` | texto | O repositório `owner/name` ao qual o pull request pertence |
| `id`, `title`, `url` | texto | Número, título e URL web do pull request (igual aos campos `pull_request_*`) |
| `pull_request_number` | número | Número do pull request |
| `pull_request_title`, `pull_request_body`, `pull_request_url` | texto | Título, descrição, URL web |
| `pull_request_author` | texto | Login do autor, por exemplo `app/dependabot` |
| `pull_request_labels` | lista | Nomes das labels |
| `pull_request_assignees` | lista | Logins dos responsáveis |
| `pull_request_milestone` | texto | Título do milestone, ou vazio |
| `pull_request_created_at` | texto | Timestamp ISO |
| `pull_request_head_ref`, `pull_request_base_ref` | texto | Nomes das branches de origem e de destino |
| `pull_request_head_sha` | texto | Id do commit do head |
| `pull_request_is_draft` | booleano | Pull request em rascunho |
| `pull_request_mergeable` | texto | `MERGEABLE`, `CONFLICTING` ou `UNKNOWN` |
| `pull_request_merge_state_status` | texto | `CLEAN`, `BLOCKED`, `BEHIND`, `DIRTY`, `DRAFT`, `HAS_HOOKS`, `UNSTABLE`, `UNKNOWN` |
| `pull_request_changed_files`, `pull_request_additions`, `pull_request_deletions` | número | Tamanho da mudança |
| `pull_request_closing_issues` | lista | URLs das issues que o pull request fecha |

## Itens de projeto (`github-project-items`) { #project-items }

Issues e pull requests compartilham os nomes `item_*`, então um único prompt funciona para ambos.

| Campo | Tipo | Significado |
| --- | --- | --- |
| `repo` | texto | O repositório `owner/name` ao qual o item pertence |
| `id`, `title`, `url` | texto | `owner/name#number`, o título e a URL web |
| `item_type` | texto | `issue` ou `pull_request` |
| `item_number`, `item_title`, `item_body`, `item_url`, `item_state` | texto ou número | Mesmo significado que para issues |
| `item_author` | texto | Login do autor |
| `item_labels`, `item_assignees` | lista | Nomes das labels e logins dos responsáveis |
| `item_milestone` | texto | Título do milestone, ou vazio |
| `item_created_at` | texto | Timestamp ISO |
| `project_title`, `project_url` | texto | O board |
| `project_column` | texto | A coluna (valor de `status_field`) em que o item foi encontrado |
| `project_fields` | texto (JSON) | Todos os valores de campos do card, por exemplo `{"Status": "Ready", "Priority": "P1"}`. Use `project_fields \| fromjson` |
| `pull_request_head_ref`, `pull_request_base_ref`, `pull_request_head_sha` | texto | Apenas para pull requests, vazio caso contrário |
| `pull_request_is_draft` | booleano | Só faz sentido para pull requests |

## Deixado de fora de propósito { #left-out-on-purpose }

Comentários, horário de atualização, estado do CI e da revisão, pull requests vinculados e revisores
solicitados não são campos. O host calcula o hash de todo campo que um trigger retorna para formar a identidade
da tarefa ([Deduplicação](github.md#deduplication)), então um valor que muda sozinho, ou porque o
agente trabalhou no item, iniciaria a mesma issue novamente. Peça ao agente que leia o que ele precisa,
por exemplo `gh issue view ${issue_number} --comments` ou `gh pr checks ${pull_request_number}`.
O estado do CI e da revisão ainda pode ser usado para *selecionar* pull requests com os filtros `ci_status` e
`review`.

## Valores opcionais

Um campo que não tem valor para o item é **texto vazio** (por exemplo, o milestone de uma issue
que não tem um), então `{{ issue_milestone or "none" }}` funciona. Um campo que não se aplica ao item de
forma alguma (por exemplo, `pull_request_head_ref` para uma issue em um projeto) também fica vazio.
