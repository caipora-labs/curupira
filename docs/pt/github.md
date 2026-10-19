# Issues e pull requests do GitHub

O Curupira descobre issues e pull requests do GitHub com filtros tipados em TOML, compila-os
em consultas da [GitHub Search](https://docs.github.com/en/search-github/searching-on-github/searching-issues-and-pull-requests)
e executa essas consultas pela API GraphQL. A autenticação é um bearer token obtido de
`gh auth token`. O Curupira não cria, edita, fecha nem comenta em issues ou pull
requests.

Cada resultado vira uma **tarefa**: um item tipado (campos de issue ou de pull request), uma
identidade usada para deduplicação, um prompt renderizado para uma CLI de agente de código e
um checkout ou worktree Git local onde esse agente roda.

| Tipo de trigger | O que ele descobre |
| --- | --- |
| `plugins-py/github-issues` | Issues em um único `owner/repository` |
| `plugins-py/github-pull-requests` | Pull requests em um único `owner/repository` |
| `plugins-py/github-project-items` | Issues e pull requests em uma coluna de um board do GitHub Projects. Veja [GitHub Projects](github-projects.md) |

## Pré-requisitos { #prerequisites }

1. Instale a [GitHub CLI](https://cli.github.com/) (`gh`).
2. Autentique-se uma vez:

   ```sh
   gh auth login
   ```

3. Confirme que o `gh` tem um token (o Curupira o lê com o mesmo comando):

   ```sh
   gh auth token
   ```

O Curupira não armazena credenciais do GitHub. Ele executa `gh auth token` (com cache de cinco
minutos) e envia esse bearer token para `https://api.github.com/graphql`. As operações de clone
e worktree usam o `git` nativo e suas credenciais Git normais para o `remote` do repositório, não
`gh repo clone`.

### Escopos do token { #token-scopes }

Use um token com o escopo `repo` para repositórios privados, ou `public_repo` quando você só
precisar de repositórios públicos. Veja `gh auth status` para saber os escopos do seu login atual.
O próprio Curupira apenas lê resultados da Search; o agente de código que ele inicia pode fazer mais,
dependendo do perfil. Veja
[o guia de autenticação do GraphQL do GitHub](https://docs.github.com/en/graphql/guides/forming-calls-with-graphql#authenticating-with-graphql)
para entender como os dados solicitados se relacionam com os escopos.

## Automação mínima de issues { #minimal-issue-automation }

Em uma automação, `repo` é o `owner/name` do GitHub que o Curupira pesquisa. `repository` é
o alias de um checkout `[repositories.<alias>]` onde o agente roda. Eles podem ser diferentes.

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

Valide sem contatar o GitHub:

```sh
curupira --config path/to/settings.toml validate
```

## Automação mínima de pull requests { #minimal-pull-request-automation }

`repo` e `repository` têm o mesmo significado de [Automação mínima de issues](#minimal-issue-automation).

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

## Automação de pull requests do Dependabot { #dependabot-pull-request-automation }

Filtre por um único autor com `author = "app/dependabot"` e exija `mergeable = true` para que
pull requests com conflito sejam ignorados. O prompt abaixo usa apenas placeholders listados acima,
e `${repo}` carrega o `owner/name` usado em todos os comandos `gh`. O perfil do agente precisa de
`auto_approve = true` para que as escritas do `gh` sem supervisão (push, `gh pr merge`) não parem para aprovação.

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

Execute até que os pull requests abertos do Dependabot sejam tratados:

```sh
curupira --config path/to/settings.toml run --watch --size 12
```

## Primeira execução { #first-run }

1. Instale e autentique a CLI do agente de código indicada pelo seu perfil (`opencode` nos
   trechos acima). As opções nativas de cada provider e as notas de configuração estão nas páginas
   [Providers e agentes](providers.md).
2. Faça uma prévia de uma tarefa correspondente, sem clonar nem iniciar um agente:

   ```sh
   curupira --config path/to/settings.toml run --dry-run
   ```

3. Esvazie as tarefas atualmente disponíveis uma vez, ou consulte continuamente:

   ```sh
   curupira --config path/to/settings.toml run
   curupira --config path/to/settings.toml run --watch
   ```

`--dry-run` não pode ser combinado com `--watch` nem com `--size`. `validate` verifica a
estrutura do TOML e a configuração do trigger sem chamar o GitHub; `run` e `run --watch` exigem
`gh` e a CLI do agente escolhido instalados e autenticados.

## Campos de configuração { #configuration-fields }

Os modelos rejeitam chaves desconhecidas.

### Campos compartilhados da automação { #shared-automation-fields }

| Campo | Padrão | Observações |
| --- | --- | --- |
| `trigger_type` | veja as observações | Defina explicitamente como `"plugins-py/github-issues"` ou `"plugins-py/github-pull-requests"`. Se omitido ao interpretar o TOML, o Curupira escolhe `"plugins-py/github-issues"` somente quando a tabela não tem `schedule`; uma chave `schedule` faz o padrão ser `"cron"` |
| `repository` | *(obrigatório)* | Alias de uma entrada `[repositories.<alias>]` |
| `checkout` | `"worktree"` | `"worktree"` ou `"main"` (checkout compartilhado, não o nome de uma branch) |
| `prompt` | *(obrigatório)* | `string.Template` não vazio com `${placeholders}` |
| `profile` | `None` | Perfil de CLI nomeado; caso contrário, `agents.defaults.profile`, cujo padrão é `"opencode"`. Veja [Providers e agentes](providers.md) para as opções de perfil |

### Filtros compartilhados do GitHub { #shared-github-filters }

Compilados na consulta da Search.

| Campo | Padrão | Qualificador da Search / comportamento |
| --- | --- | --- |
| `repo` | *(obrigatório)* | `repo:owner/name` (formato `owner/repository`) |
| `state` | `"open"` | `"open"` → `is:open`; `"closed"` → `is:closed`; `"all"` → nenhum dos dois. Para pull requests, `is:closed` inclui PRs com merge feito |
| `labels` | `()` | Uma label ou uma lista. Cada valor → `label:…` (AND: todas as labels devem estar presentes) |
| `exclude_labels` | `()` | Uma label ou uma lista. Cada valor → `-label:…` |
| `assignee` | `None` | Login, `@me`, `none` → `no:assignee`, ou `any` → `assignee:*` |
| `author` | `None` | `author:…` |
| `milestone` | `None` | `milestone:…` |
| `project` | `None` | `project:<value>`, por exemplo `acme/5` |
| `sort` | `"created-asc"` | Adicionado como `sort:…`. Permitidos: `created-asc`, `created-desc`, `updated-asc`, `updated-desc`, `comments-asc`, `comments-desc` |

O qualificador `project` apenas restringe a qual projeto um item pertence. Para escolher itens por
coluna do board, use [`github-project-items`](github-projects.md). Valores com espaço em branco ou `"`, `:`, `,` são colocados entre aspas na
consulta compilada.

### Campos exclusivos de issues { #issue-only-fields }

| Campo | Padrão | Comportamento |
| --- | --- | --- |
| `linked_pull_request` | `None` | `true` → `linked:pr`; `false` → `-linked:pr`; omita para não filtrar |

### Campos exclusivos de pull requests { #pull-request-only-fields }

| Campo | Padrão | Comportamento |
| --- | --- | --- |
| `draft` | `None` | `true` → `draft:true`; `false` → `draft:false` |
| `base` | `None` | `base:…` |
| `head` | `None` | `head:…` |
| `review` | `None` | `review:…` — `none`, `required`, `approved` ou `changes_requested` |
| `ci_status` | `None` | `status:…` — `success`, `failure` ou `pending` |
| `linked_issue` | `None` | `true` → `linked:issue`; `false` → `-linked:issue` |
| `mergeable` | `None` | Pós-filtro do GraphQL: `true` mantém `MERGEABLE`; `false` mantém `CONFLICTING` |
| `merge_state` | `()` | Pós-filtro do GraphQL: mantém apenas os valores de `mergeStateStatus` listados (`BEHIND`, `BLOCKED`, `CLEAN`, `DIRTY`, `DRAFT`, `HAS_HOOKS`, `UNKNOWN`, `UNSTABLE`) |

`mergeable` e `merge_state` são aplicados depois que a Search retorna os resultados; não são
qualificadores da Search.

### Configurações de polling relacionadas { #related-polling-settings }

Em `[settings.polling]`:

| Campo | Padrão |
| --- | --- |
| `poll_interval_seconds` | `30.0` |
| `batch_size` | `100` (máximo 1000) |
| `cron_poll_interval_seconds` | `1.0` |

## Como issues e pull requests são selecionados { #how-issues-and-pull-requests-are-selected }

Cada poll monta uma consulta que sempre começa com `repo:<repo>` e com `is:issue` ou
`is:pr`, depois acrescenta os filtros acima e `sort:<sort>`. Exemplo para a automação mínima
de issues:

```text
repo:acme/api is:issue is:open label:agent-ready -linked:pr sort:created-asc
```

A descoberta usa a Search do GraphQL (o tipo de busca `ISSUE` cobre tanto issues quanto pull requests).
Não existe um campo `query` livre: os filtros são apenas TOML tipado.

### Deduplicação { #deduplication }

O host identifica um resultado fazendo o hash da lista de chaves/valores que o trigger retornou, nessa
ordem, junto com a automação, o repositório e o tipo do trigger.
O Curupira não guarda histórico de issues nem de pull requests:

- **Sem duplicatas numa execução.** Um `run --watch` ou `tui` em andamento despacha cada tarefa
  uma vez, termine ela com sucesso ou com falha. Uma consulta posterior que retorne os mesmos pares
  é ignorada até o processo terminar.
- **Nada é lembrado entre execuções.** O Curupira não registra issues nem pull requests
  concluídos. Depois de uma reinicialização, todo item que ainda corresponda aos filtros do
  trigger é despachado de novo, então os filtros decidem o que está pendente.
- **Trabalho interrompido é retomado.** Este é o único estado de tarefa que o Curupira guarda. O
  id da sessão do agente de código é salvo em `state_db_path` assim que o agente o informa, e
  removido quando a tarefa termina com sucesso. Quando o Curupira reinicia no meio de uma tarefa
  (ou a tarefa falhou ou estourou o tempo), o próximo despacho continua essa sessão com as mesmas
  instruções em vez de recomeçar. Um prompt de automação alterado começa uma sessão nova.

Alterar qualquer valor retornado, inclusive o título, o corpo ou as labels, cria uma tarefa diferente. Por
isso os triggers do GitHub não retornam valores que mudam sozinhos ou porque o agente trabalhou no item
(comentários, horário de atualização, estado do CI e da revisão, pull requests vinculados):
o agente seria iniciado novamente para a mesma issue. Quando o agente precisar deles, diga a ele que os leia,
por exemplo com `gh issue view ${issue_number} --comments`.

A chave é por automação, então duas automações podem processar a mesma issue ou o mesmo pull request com
prompts diferentes. `run --dry-run` faz a prévia sem despachar.

!!! tip "Manter itens concluídos de fora"
    Filtre por um estado que o agente altera, e faça o prompt pedir que ele o altere ao
    terminar: feche o item, adicione ou remova uma label (`exclude_labels = ["blocked"]`) ou
    vincule um pull request (`linked_pull_request = false`).

Quando um ciclo completo não encontra nada (ou a descoberta falha), o feed espera
`poll_interval_seconds` e depois dobra a espera a cada ciclo vazio consecutivo, até cinco
minutos (`300` segundos). Qualquer descoberta bem-sucedida reinicia o intervalo.

## O que o prompt do agente recebe { #what-the-agent-prompt-receives }

O prompt pode usar `${field}` ou a sintaxe Jinja; veja [Escrevendo prompts](prompts.md). Todos os campos
de issues e pull requests (título, corpo, labels, responsáveis, milestone, tamanho do diff e mais) estão listados na [Referência de campos de prompt](prompt-fields.md).

## Segurança: o texto de issues e pull requests não é confiável { #security }

Títulos e corpos (`${issue_title}`, `${issue_body}`, `${pull_request_title}`,
`${pull_request_body}`, `${item_body}`) vêm de qualquer pessoa que possa abrir uma issue ou um pull request e são
colocados no prompt do agente de código, então um autor hostil pode tentar manipular o agente
(prompt injection). O agente pode executar ações destrutivas no checkout em que trabalha,
então o risco depende do que você permite no perfil do agente. Restrinja o que chega ao
agente com `labels` (aplicadas somente por pessoas em quem você confia), `author` ou `assignee`, e
revise o que o seu perfil de agente tem permissão para executar.

## Checkout e worktrees { #checkout-and-worktrees }

Os triggers do GitHub usam o controle de versão Git nativo padrão.

1. O Curupira clona `repositories.<alias>.remote` em `workspace_dir/<alias>` (ou no
   `path` do alias) no primeiro uso.
2. Com `checkout = "worktree"` (padrão), ele faz fetch de `origin`, resolve a branch padrão
   remota e adiciona uma worktree em
   `<checkout>.worktrees/<automation_id>/<task_type>-<sha256(task_id)>` na branch
   `curupira/<automation_id>/<task_type>-<sha256(task_id)>`. A branch não é enviada com push.
3. Com `checkout = "main"`, o agente roda no checkout compartilhado como está: sem fetch, pull nem
   troca de branch.
4. Depois que o agente termina, o Curupira remove a worktree e apaga a branch local
   (falhas na limpeza são registradas em log, não são fatais).

O `setup_script` opcional no alias do repositório roda somente após um clone novo do
checkout base, não dentro da worktree.

### Isolamento do agente { #agent-isolation }

O processo do agente roda com o diretório de trabalho e o `PWD` definidos para a worktree, e sem
as variáveis `GIT_DIR`, `GIT_WORK_TREE` e `GIT_INDEX_FILE` que apontariam o Git para outro
repositório. O seu próprio checkout nunca é alterado por uma automação. O OpenCode 1.x também
recebe `--dir <worktree>`. O OpenCode 2.x não tem `--dir`; uma execução headless usa a worktree
como diretório de trabalho e passa `--standalone`, então a tarefa não entra no serviço em
segundo plano compartilhado. O OpenCode 1.x também recebe
`OPENCODE_DB` definido como `<worktree>.opencode.db`, para que as sessões e as entradas de projeto
fiquem com aquela tarefa. O OpenCode 2.x mantém o seu banco, onde guarda as credenciais dos
provedores. Outros estados globais do agente, como a configuração global do OpenCode, são
compartilhados.

## Erros comuns { #common-errors }

| Sintoma | Causa provável | Correção |
| --- | --- | --- |
| `Required executable not found: gh` | GitHub CLI ausente do `PATH` | Instale o `gh` e tente de novo |
| `gh exited with status …` / token vazio | Sem login, ou token indisponível | Execute `gh auth login` e depois `gh auth token` |
| GraphQL / HTTP 401 ou erros de escopo | O token não tem acesso ao repositório ou à Search | Execute `gh auth login` de novo para que o token inclua `repo`, ou use um PAT clássico com os escopos exigidos pelo [guia do GraphQL do GitHub](https://docs.github.com/en/graphql/guides/forming-calls-with-graphql#authenticating-with-graphql) |
| No tasks scheduled | Os filtros não encontram nada | Amplie labels/state, remova filtros `linked_*` / `draft`, ou confirme que `repo` está correto; ciclos vazios não são um erro |
| `GitHub GraphQL temporarily failed with status 429` (ou similar) | Limite de taxa ou falha transitória da API | O Curupira tenta novamente erros transitórios algumas vezes; espere ou reduza a frequência de polling / `batch_size` |
| Avisos de descoberta em `run --watch` | Falha do GraphQL ou da CLI tratada como ciclo vazio | Verifique os logs por `Discovery failed for …`; corrija a autenticação ou a rede e aguarde o próximo poll |

`curupira validate` verifica a estrutura do TOML e a configuração do trigger sem chamar o GitHub.
`curupira run` e `curupira run --watch` exigem o `gh` instalado e autenticado.
