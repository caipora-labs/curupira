# gh-dispatch

Ferramenta de terminal que observa issues e pull requests do GitHub, agenda tarefas
por cron e inicia coding agents com limite configurável de concorrência.

## Requisitos

- Python 3.11 ou superior
- [`gh`](https://cli.github.com/) instalado e autenticado (`gh auth login`)
- CLI do coding agent usado pelos perfis configurados: [`opencode`](https://opencode.ai/),
  [`codex`](https://developers.openai.com/codex/cli/), [`claude`](https://code.claude.com/docs/en/cli-reference)
  ou Cursor CLI (`agent`)

## Instalação para desenvolvimento

```bash
uv sync --dev --no-editable
uv run --no-sync gh-dispatch --help
```

Para instalar o executável como ferramenta no ambiente do usuário:

```bash
uv tool install .
```

## Configuração

Copie `gh-dispatch.example.toml` para `gh-dispatch.toml` e ajuste os repositórios,
caminhos, queries e prompts. O caminho padrão é `./gh-dispatch.toml`; outro arquivo
pode ser indicado com `--config`.

```toml
[core]
max_active_tasks = 1
workspace_dir = "~/.gh-dispatch/workspaces"
# state_db_path = "~/.gh-dispatch/state.sqlite3" # estado das sessões em execução

[watchers.issues]
poll_interval_seconds = 30
batch_size = 100

[[watchers.issues.repositories]]
repo = "acme/api"
query = "is:open label:agent-ready sort:created-asc"
# path = "~/code/api" # opcional: clone existente ou destino alternativo
# coding_agent = "opencode-fast" # opcional: perfil específico para este repositório

[watchers.pull_requests]
poll_interval_seconds = 30
batch_size = 100

[[watchers.pull_requests.repositories]]
repo = "acme/api"
query = "is:open label:review-needed"

[watchers.cron]
poll_interval_seconds = 1

[[watchers.cron.jobs]]
id = "weekly-maintenance"
schedule = "0 9 * * 1"
timezone = "Europe/Rome"
# start_date = 2026-10-05T00:00:00+02:00
# end_date = 2026-12-31T23:59:00+01:00
repo = "acme/api"
prompt = "Faça a manutenção semanal de ${repo} (execução ${task_number})."
coding_agent = "opencode-default"

[agent]
prompt = """
Trabalhe na issue ${issue_number}: ${issue_title}

${issue_body}

Repositório: ${repo}
URL: ${issue_url}
"""
pull_request_prompt = """
Revise o pull request ${pull_request_number}: ${pull_request_title}

${pull_request_body}

Repositório: ${repo}
URL: ${pull_request_url}
Branch: ${pull_request_head_ref} -> ${pull_request_base_ref}
"""

[coding_agents]
default = "opencode-default"

[coding_agents.profiles.opencode-default]
provider = "opencode"
# model = "provider/model" # opcional; usa o default do OpenCode se omitido
# agent = "build"          # opcional; usa o default do OpenCode se omitido
# effort = "high"          # opcional; mapeado para --variant

[coding_agents.profiles.opencode-fast]
provider = "opencode"
model = "provider/fast-model"
agent = "build"
effort = "low"

[coding_agents.profiles.codex]
provider = "codex"
# model = "gpt-5.4"
# agent = "my-codex-config-profile" # mapeado para --profile
effort = "high"

[coding_agents.profiles.claude-code]
provider = "claude"
model = "sonnet"
# agent = "reviewer"
effort = "high"

[coding_agents.profiles.cursor]
provider = "cursor"
# model = "composer-2.5"
agent = "plan" # Cursor aceita agent, ask e plan; agent é o padrão
```

As queries usam a sintaxe de busca do GitHub. Os watchers de issues e pull requests
consultam seus repositórios sequencialmente pela CLI, na ordem do arquivo, mesmo quando
ainda não há clone local, e buscam até `batch_size` itens por consulta (100 por padrão,
configurável até 1000). Quando uma tarefa for despachada, `gh repo clone` prepara o
checkout em `workspace_dir/owner/repo`. O `path` opcional pode apontar para um clone
existente ou definir um destino alternativo; caminhos relativos são resolvidos em
relação ao TOML, assim como `workspace_dir`. Repositórios podem definir um prompt
próprio opcional, que substitui o prompt padrão do respectivo tipo de tarefa.
`[coding_agents].default` seleciona o perfil global. Cada repositório pode indicar um
perfil diferente com `coding_agent = "nome-do-perfil"`; todas as issues e pull requests
daquele repositório herdam esse perfil.

Os providers disponíveis são `opencode`, `codex`, `claude` e `cursor`. O adapter Codex
usa `codex exec --json` e retoma threads pelo ID; `agent` seleciona um perfil Codex e
`effort` configura `model_reasoning_effort`. Claude Code usa `claude -p` com eventos
JSON em streaming, retomada por `--resume`, `--agent` e `--effort`. Cursor usa o
executável `agent`, `--print`, `--output-format stream-json` e `--resume`; seu campo
`agent` seleciona o modo `agent`, `ask` ou `plan`. Cursor não aceita `effort`.

### Tarefas agendadas por cron

Cada `[[watchers.cron.jobs]]` define uma tarefa independente com `id`, expressão cron
de cinco campos, `timezone` IANA, `repo`, `prompt` e as mesmas opções de caminho e
perfil usadas pelos watchers de repositório. `start_date` e `end_date` são opcionais,
inclusivos e interpretados no timezone do job. Sem `start_date`, o início é a data em
que o app registrou o job pela primeira vez; essa data fica persistida no SQLite.

Quando há uma ou mais ocorrências vencidas, elas são coalescidas em uma única execução
assim que possível, sem reproduzir cada ocorrência perdida. O mesmo job não roda em
paralelo consigo mesmo; se estiver ocupado, uma ocorrência pendente aguarda o término.
As tarefas cron passam pelo mesmo limite `max_active_tasks`, scheduler, checkout e
recuperação de sessões das issues e pull requests. A última execução e a ocorrência
pendente são persistidas no banco local.

`max_active_tasks` é o limite de processos de coding agents em execução simultânea e assume
`1` quando `[core]` ou o campo não são informados. O polling aguarda
`poll_interval_seconds` — 30 segundos por padrão — somente quando um ciclo completo
não encontra tarefas novas. Esperas consecutivas sem resultados dobram o intervalo
até o máximo de 5 minutos; encontrar tarefas novas reinicia o backoff. Tarefas são
deduplicadas em memória durante a vida do processo; reiniciar o watcher pode despachar
novamente uma tarefa elegível que já terminou. Sessões de coding agents ainda em execução são
salvas no SQLite. Após um reinício inesperado, `watch` retoma todas as sessões salvas;
`run` retoma a sessão salva da issue que selecionar.

O banco local fica em `~/.gh-dispatch/state.sqlite3` por padrão; `core.state_db_path`
pode apontar para outro arquivo (caminhos relativos são resolvidos a partir do TOML).
O SQLite guarda uma chave composta privada e o conteúdo JSON do modelo da sessão. As
sessões ativas não expiram por TTL; o registro é removido quando o processo do agent
termina. Se o esquema do banco local for incompatível, ele é recriado sem migrations.

Placeholders comuns: `${repo}`, `${task_type}`, `${task_number}`, `${task_title}`,
`${task_body}` e `${task_url}`. Há também placeholders específicos `${issue_number}`,
`${issue_title}`, `${issue_body}`, `${issue_url}` e `${pull_request_number}`,
`${pull_request_title}`, `${pull_request_body}`, `${pull_request_url}`,
`${pull_request_is_draft}`, `${pull_request_head_ref}` e `${pull_request_base_ref}`.

### Filtrar por status de um project board

O único parâmetro de busca é `query`. Para queries que usam o qualificador `project:`,
o client mantém o estado `open`, solicita `projectItems` e filtra automaticamente o
status `Todo`:

```toml
[[watchers.issues.repositories]]
repo = "mariotaddeucci/bob"
query = "project:mariotaddeucci/5"
```

O client executa `gh issue list --state open --search ... --json number,title,url,projectItems`
e aplica o filtro `jq` internamente. As outras queries usam os campos padrão de issues.
O resultado é validado mesmo quando o `jq` produz objetos JSON em linhas separadas.

## Uso

Validar a configuração sem chamar as CLIs:

```bash
gh-dispatch --config gh-dispatch.toml validate
```

Despachar uma issue e esperar o coding agent terminar:

```bash
gh-dispatch --config gh-dispatch.toml run
```

Ver qual issue seria selecionada sem iniciar o coding agent:

```bash
gh-dispatch --config gh-dispatch.toml run --dry-run
```

Iniciar os watchers configurados (issues e pull requests), os jobs cron e o scheduler
limitado por `max_active_tasks`:

```bash
gh-dispatch --config gh-dispatch.toml watch
```

O modo `watch` usa o modo não interativo de cada CLI para que múltiplos workers não disputem a
TUI do terminal. O app clona repositórios sob demanda usando a CLI do GitHub; não cria
branches/worktrees nem modifica issues. O CLI selecionado trabalha no checkout criado
no workspace ou no caminho `path` configurado.

PyResilience aplica retries com backoff às falhas transitórias das consultas do
GitHub CLI. Falhas de autenticação, configuração ou formato não são repetidas; uma
tarefa de coding agent também não é repetida automaticamente.

## Desenvolvimento e validação

```bash
uv run --no-sync pytest
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pyrefly check
uv build
```
