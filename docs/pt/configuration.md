# Configuração

O Curupira lê um único arquivo TOML, `~/.curupira/settings.toml` por padrão (`--config` escolhe
outro). Ele tem seis tipos de tabela:

| Tabela | O que declara |
| --- | --- |
| `[settings]` | Limites de execução, caminhos e consultas |
| `[environment]` | Variáveis copiadas para cada processo que o Curupira inicia |
| `[repositories.<alias>]` | Remotes Git em que os agentes trabalham |
| `[agents]` | O perfil padrão e uma tabela por perfil de agente |
| `[plugins.<alias>]` | Pacotes de fontes de tarefas e como iniciá-los |
| `[automations.<name>]` | O que observar, onde trabalhar, qual agente e o prompt |

Os nomes depois do ponto (`api`, `claude`, `plugins-py`, `resolve-ready-issues`) são
escolhidos por você. Execute `curupira validate` depois de cada mudança.

## Um arquivo completo { #example }

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

## Settings { #settings }

Todas as chaves são opcionais.

| Chave | Padrão | Significado |
| --- | --- | --- |
| `max_active_tasks` | `1` | Agentes que podem rodar ao mesmo tempo. |
| `workspace_dir` | `~/.curupira/workspaces` | Onde os repositórios são clonados. |
| `state_db_path` | `~/.curupira/state.sqlite3` | Tarefas concluídas, ocorrências do cron e sessões retomáveis. |
| `log_level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` ou `CRITICAL`. `--log-level` o substitui. |
| `task_timeout_minutes` | `20` | Prazo de uma execução do agente e do `setup_script`. |
| `max_output_bytes` | `1000000` | Saída mantida de cada execução do agente e do script de setup. |
| `polling.poll_interval_seconds` | `30` | Pausa entre consultas em `run --watch` e `tui`. |
| `polling.batch_size` | `100` | Itens solicitados a cada trigger por consulta. |

Caminhos relativos são resolvidos a partir do diretório do arquivo de configuração.

## Ambiente { #environment }

Todo processo que o Curupira inicia — agentes de código, Git, `setup_script` e extensões — recebe uma cópia de cada variável de ambiente que o processo Curupira enxerga. `[environment.vars]` substitui esses valores. Omita a tabela para repassar o ambiente do processo sem alterações.

Os valores são strings literais. `$VAR` e `${VAR}` não são expandidos.

O Curupira ainda define o diretório de trabalho (`PWD`) e remove as variáveis que amarram um repositório (`GIT_DIR` e os outros vínculos `GIT_*`) depois desses overwrites, e as variáveis próprias de um agente (por exemplo `OPENCODE_DB`) são aplicadas depois de `[environment.vars]`.

```toml
[environment.vars]
HTTPS_PROXY = "http://proxy.internal:8080"
GITHUB_TOKEN = "ghp_..."
```

| Chave | Significado |
| --- | --- |
| `vars` | Nomes de variáveis de ambiente e os valores que as substituem. Vazio quando omitido. Os nomes seguem `[A-Za-z_][A-Za-z0-9_]*`. |

## Repositórios { #repositories }

`[repositories.<alias>]` é um checkout Git em que uma ou mais automações trabalham.

| Chave | Obrigatória | Significado |
| --- | --- | --- |
| `remote` | sim | A URL para o `git clone`: HTTPS, SSH ou `user@host:path`. |
| `path` | não | Usa ou cria o checkout aqui em vez de `workspace_dir/<alias>`. |
| `setup_script` | não | Um executável relativo ao repositório, executado uma vez logo após um clone novo. |

O remote não precisa estar no GitHub: o filtro `repo` do trigger decide o que é
observado, e `remote` decide onde o agente trabalha. Os clones usam as suas credenciais Git
normais.

## Agentes { #agents }

```toml
[agents.defaults]
profile = "claude"    # usado pelas automações que não definem um perfil
timezone = "UTC"      # fuso horário padrão das automações cron

[agents.profiles.claude]
provider = "claude"
model = "sonnet"
```

Cada perfil define um `provider`: `claude`, `codex`, `copilot`, `cursor`, `gemini`, `kilo`,
`opencode`, `pi` ou `qwen`. As outras chaves são opções desse agente; veja
[Agentes de código](providers.md) para todas as opções e a flag nativa em que cada uma se transforma.

## Assistente { #assistant }

`[assistant]` é opcional e reservada para o assistente interativo do
[painel no terminal](tui.md#assistant).

| Chave | Significado |
| --- | --- |
| `agent` | Um nome de provider embutido. `curupira validate` rejeita nomes desconhecidos. |
| `model` | Um id de modelo para esse agente. Omita para usar o padrão do agente. |

## Plugins { #plugins }

`[plugins.<alias>]` registra um pacote de triggers e como iniciá-lo. As automações então
usam `trigger_type = "<alias>/<trigger>"`.

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

| Chave | Obrigatória | Significado |
| --- | --- | --- |
| `type` | sim | `uvx` ou `npx`. Esse launcher precisa estar no `PATH`. |
| `args` | sim | Argumentos depois do launcher, passados como lista e nunca por um shell. Fixe as versões. |
| `tools` | não | Padrões glob que selecionam triggers. `!` exclui. Vazio mantém todos os triggers. |

Conectores como o do GitHub, e os que estão em desenvolvimento, estão listados em
[Plugins e conectores](plugins.md). Para escrever o seu, veja
[Desenvolver extensões](extensions.md) e o [SDK JavaScript](extensions-javascript.md).

## Automações { #automations }

`[automations.<name>]` liga um trigger a um repositório, a um agente e a um prompt.

| Chave | Obrigatória | Significado |
| --- | --- | --- |
| `trigger_type` | sim | `<alias>/<trigger>` de um plugin, ou `cron`. |
| `repository` | sim | Um nome de `[repositories.<alias>]`. |
| `prompt` | sim | A mensagem para o agente. Veja [Escrevendo prompts](prompts.md). |
| `profile` | não | Um nome de perfil. O padrão é `[agents.defaults].profile`. |
| `checkout` | não | `worktree` (padrão) ou `main`. Veja [Checkout e setup](#checkout). |

Todas as outras chaves são passadas ao trigger como as configurações dele. O trigger do GitHub
recebe `repo`, `labels` e outros filtros, documentados em [Issues e pull requests](github.md) e
[Projects](github-projects.md). O cron recebe `schedule` e as chaves descritas em
[Cron](automations.md#cron).

As automações são consultadas na ordem do arquivo. Placeholders e condições de prompt são tratados em
[Escrevendo prompts](prompts.md); a [Referência de campos do prompt](prompt-fields.md) lista o que cada
trigger fornece.

## Checkout e setup { #checkout }

Por padrão, cada tarefa recebe o seu próprio worktree e branch ao lado do clone
(`<clone>.worktrees/<automation>/…`, branch `curupira/<automation>/…`). O worktree é
removido quando a tarefa termina, então as tarefas nunca compartilham arquivos.

`checkout = "main"` executa o agente no clone compartilhado. Nesse modo, o Curupira não faz fetch,
pull nem troca de branch; use-o para jobs somente leitura ou agendados que devem
ver o clone como ele está.

O `setup_script` roda apenas após um clone novo, no clone, nunca em um worktree. Uma
saída diferente de zero interrompe a tarefa. `run --dry-run` nunca clona nem executa o setup.

## Agendamento e estado { #scheduling-and-state }

Cada consulta pede ao trigger de cada automação até `batch_size` itens. Os campos de
cada item geram um hash que vira a identidade da tarefa:

- Uma tarefa que terminou `ok` é armazenada em `state_db_path` e nunca roda de novo.
- O mesmo item com um campo alterado (um novo título, um novo commit no head) é uma nova identidade,
  então pode rodar de novo.
- Uma tarefa que falhou não é repetida no mesmo processo; o próximo `run` tenta de novo.

Filtros como `linked_pull_request = false` decidem o que o trigger do GitHub retorna; veja
[Deduplicação](github.md#deduplication) para saber como os triggers do GitHub mantêm a sua saída
estável. Automações cron produzem uma ocorrência quando o agendamento vence e nunca rodam
duas vezes ao mesmo tempo.

Apenas um processo `run` ou `tui` despacha por vez; ele mantém o
`~/.curupira/dispatch.lock`. Um banco de estado incompatível é um erro e nunca é apagado
automaticamente.
