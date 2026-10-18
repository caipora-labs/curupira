# Configuração

## Referência gerada dos modelos

A referência dos modelos abaixo é gerada a partir dos modelos Pydantic públicos. Os tipos dos campos,
os valores padrão e as restrições vêm diretamente dos modelos de origem; atualize esses modelos em vez de
manter aqui uma tabela de campos paralela.

### Configurações de execução

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

### Repositórios, agentes e automações

::: curupira.models.configuration.RepositoryConfiguration

::: curupira.models.configuration.AgentDefaults

::: curupira.models.configuration.AgentsSettings

::: curupira.models.configuration.AssistantSettings

::: curupira.models.configuration.IssueAutomationConfiguration

::: curupira.models.configuration.PullRequestAutomationConfiguration

::: curupira.models.configuration.CronAutomationConfiguration

### Profiles de CLI

::: curupira.models.profiles.OpenCodeCliProfile

::: curupira.models.profiles.CodexCliProfile

::: curupira.models.profiles.ClaudeCodeCliProfile

::: curupira.models.profiles.CursorCliProfile

O profile da GitHub Copilot CLI está documentado na sua [página do provider](providers/copilot.md#configuration-reference).

Um único arquivo TOML separa os limites de execução, os repositórios Git, os profiles de agentes de código e
as automações. Uma automação observa issues, pull requests, cards ou um agendamento cron, e
aponta para um alias de repositório para o checkout.

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

Salve isto como `~/.curupira/settings.toml`. As chaves sob `repositories`, `profiles`,
`plugins` e `automations` são identificadores escolhidos por você; `repository` liga uma
automação a um alias de checkout, `profile` a liga a um profile de agente de código, e
`[plugins.<alias>]` registra um lançador de triggers para que as automações possam usar
`<alias>/<local-trigger>` (por exemplo `plugins-py/github-issues`).

O `provider` de cada profile seleciona um agente de código **embutido**: `claude`, `codex`, `copilot`,
`cursor`, `gemini`, `kilo`, `opencode`, `pi` ou `qwen`. Os agentes de código fazem parte da CLI
em Rust (não são extensões de processo). `curu plugins list` mostra esses providers como
`agent:<name>` com origem `built-in`, junto com as extensões de trigger.

## Assistente { #assistant }

`[assistant]` é opcional. Ele registra qual provider de agente de código embutido deve executar
o assistente de configuração interativo e qual model essa CLI deve usar:

- `agent`: o nome de um provider embutido (os mesmos identificadores usados nos valores
  de `provider` dos profiles). Deixe sem definir até escolher um.
- `model`: o id de um model concreto, ou omita-o para preferir a seleção automática nativa do
  provider quando o adaptador a documentar (`auto` para Cursor, Gemini CLI e GitHub
  Copilot CLI). O valor literal `auto` é rejeitado para providers sem essa capacidade.

Arquivos TOML existentes sem `[assistant]` mantêm os padrões não definidos.

Atualmente o `curu tui` executa o dispatch contínuo com linhas de status; um painel completo de assistente
embutido é trabalho futuro. As receitas de execução interativa de cada provider embutido ainda estão
implementadas no core em Rust para essa superfície futura.

## Plugins

`[plugins.<alias>]` registra um trigger sob um alias das configurações e declara como lançá-lo.
`uvx` e `npx` são lançadores independentes; `args` são passados a essa ferramenta como argv
(nunca como uma string de shell). O host descobre os tipos de trigger iniciando o processo e
chamando `describe`, e então aplica um filtro opcional `tools`:

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

- `type` (obrigatório): `uvx` ou `npx`.
- `args` (obrigatório, não vazio): argumentos depois do binário do lançador. Os plugins Python
  oficiais expõem um script de console `curupira-plugins`, então os usuários finais executam
  `uvx --from curupira-plugins curupira-plugins` (sem `python -m`). Plugins Node publicam
  um pacote npm cujo `bin` fala o protocolo (normalmente construído com
  [`@caipora/curupira-sdk`](extensions.md#javascript-extension));
  fixe a versão em `args` (por exemplo `@acme/curupira-ext@1.2.3`). O `npx` precisa estar no
  `PATH` (instale o [Node.js](https://nodejs.org/)).
- `tools` (opcional): lista de globs que seleciona quais nomes locais de trigger expor. Vazia ou
  omitida, mantém todos os triggers de `describe`. Padrões positivos (`github-*`, `*`) são
  inclusões; padrões que começam com `!` (`!github-project-*`) são exclusões. Um nome deve casar com uma
  inclusão quando houver inclusões definidas e não pode casar com nenhuma exclusão.

As automações então definem `trigger_type = "<alias>/<local-trigger>"`. Os nomes locais de trigger são
nomes em kebab-case declarados pela extensão (por exemplo `github-issues`). A distribuição oficial
`curupira-plugins` costuma ser registrada como `plugins-py` com `type = "uvx"`.

## Repositórios

`[repositories.<alias>]` é dono das configurações de checkout do Git compartilhadas por uma ou mais automações:

- `remote` (obrigatório): URL Git completa usada pelo `git clone` (HTTPS, SSH ou `user@host:path`).
- `path` (opcional): checkout existente ou destino alternativo do clone.
- `setup_script` (opcional): executável relativo ao repositório, executado somente após um clone novo.

A descoberta no forge é independente da URL de checkout. Um padrão comum é um `remote`
em um host diferente do GitHub com issues públicas do GitHub: defina `repositories.api.remote` com
essa URL Git e defina o `repo` do GitHub da automação como `owner/name`.

## Automações

`trigger_type` seleciona a fonte:

- `plugins-py/github-issues` descobre issues do GitHub pela GraphQL Search usando filtros tipados
  (`labels`, `exclude_labels`, `assignee`, `linked_pull_request`, `sort`, …). Defina
  `linked_pull_request = false` para que a descoberta compile `-linked:pr` e ignore issues que
  já têm um pull request vinculado. Esse filtro vale apenas para a descoberta em tempo de configuração;
  veja [Agendamento e estado](#scheduling-and-state) para a revalidação das sessões recuperadas pelo scheduler.
- `plugins-py/github-pull-requests` descobre pull requests do GitHub da mesma forma, com filtros de PR como
  `draft`, `review`, `ci_status`, além dos pós-filtros `mergeable` / `merge_state`.
- `cron` produz ocorrências a partir de um `schedule` de cinco campos em vez de consultar um forge.
- As [extensões de trigger](extensions.md) instaladas adicionam seus próprios tipos de trigger;
  `curu plugins list` mostra todos os tipos disponíveis.

Cada automação exige `repository` (alias) e `prompt`. Os triggers do GitHub também
exigem a identidade `repo` do forge (`owner/name`). O cron exige `schedule`. O `profile` opcional
seleciona um profile de CLI. Aliases de repositório diferentes não podem compartilhar o mesmo caminho de workspace. As automações mantêm
a ordem do arquivo, e a seleção de execução única segue essa ordem.

A autenticação na API do GitHub usa `gh auth token`, de uma GitHub CLI já autenticada.
A autenticação do clone usa as credenciais nativas do Git para o `remote` configurado.

Os placeholders usam a sintaxe `${name}` (condicionais e laços do Jinja também estão disponíveis; veja
[Escrevendo prompts](prompts.md)). O host sempre fornece `${repository}` (a
identidade do forge derivada do remote Git) e `${automation}` (o nome da
automação). Toda outra `${key}` vem do resultado do trigger: o SDK transforma o
objeto retornado em pares de strings, e cada chave é substituída como foi escrita,
inclusive chaves que não são identificadores comuns (`${issue-number}`). Um
placeholder sem correspondência é deixado inalterado (pode ser texto de shell, como `${HOME}`);
o `validate` só reclama quando um `${name}` ou `{{ name }}` parece um erro de digitação de uma chave real. Os plugins oficiais escolhem suas próprias chaves. As issues
do GitHub incluem `issue_number`, `issue_title`, `issue_body` e `issue_url`;
os pull requests incluem `pull_request_number`, `pull_request_title`,
`pull_request_body`, `pull_request_url`, `pull_request_is_draft`,
`pull_request_head_ref`, `pull_request_base_ref`, `pull_request_head_sha` e
`pull_request_mergeable`, entre os outros campos desse modelo. Os prompts de cron
recebem apenas as duas variáveis do host (e a forma legada `$automation`).

## Checkout e setup

Cada tarefa usa seu próprio worktree por padrão, criado a partir do branch padrão do remote buscado.
Defina `checkout = "main"` para usar o checkout compartilhado como está; o Curupira não faz fetch, pull nem
troca de branch nesse modo. O `path` do alias do repositório seleciona o checkout base.
Os clones usam `git clone <remote>`.

`setup_script` fica no alias do repositório. Ele roda diretamente somente depois que um checkout base
é clonado do zero, não para um checkout existente nem em um worktree de tarefa. Uma saída diferente de zero
impede o agente de iniciar e remove o checkout recém-clonado. A validação verifica a
sintaxe do caminho, mas não exige que o script exista. `run --dry-run` não faz fetch, clone,
não cria worktrees nem executa o setup.

## Agendamento e estado { #scheduling-and-state }

Cada consulta busca até `batch_size` itens (padrão 100, máximo 1000). Ciclos de consulta vazios aumentam o intervalo
a partir de `poll_interval_seconds` (padrão 30 segundos) até cinco minutos; uma descoberta zera
a espera. As automações fazem a deduplicação de forma independente.

Filtros de descoberta como `linked_pull_request = false` (`-linked:pr`) afetam apenas o que
a busca do GitHub devolve para trabalho novo. Eles não protegem sessões recuperadas que foram salvas
antes de uma issue ganhar um PR vinculado. A aplicação pelo scheduler é separada: antes de uma nova tarefa ou
sessão salva ser admitida, o Curupira busca o estado atual da issue ou do pull request uma vez,
descarta itens fechados ou com merge feito, rejeita uma issue que já tenha um PR de fechamento aberto ou
vinculado em Development (via GraphQL `closedByPullRequestsReferences`, incluindo formas no corpo
como `Fixes: #N`), aposenta a sessão obsoleta dessa issue e reinicia uma sessão de PR quando o
SHA do head, o flag de draft, o título ou o corpo não correspondem mais ao snapshot salvo. As sessões
de pull request recuperadas de um banco de estado gravado antes de o SHA do head ser persistido
reiniciam uma vez quando o snapshot atualizado fornece um head. Se o GitHub informar mais referências
de PR de fechamento do que cabem em uma página GraphQL, a admissão falha de forma fechada para esse candidato (sem agente). Um erro
transitório de revalidação adia esse candidato, mantém qualquer sessão salva e não interrompe o
scheduler.

As consultas de execução única e as iniciais chamam todos os feeds de automação juntos. Um `DispatchError` de um
feed é registrado no log e esse feed não contribui com tarefas; os outros feeds ainda devolvem candidatos.
O `run` (execução única) então tenta os candidatos em ordem e passa ao próximo quando a revalidação
descarta um. O `run --watch` / `tui` contínuo já registra em log os erros de descoberta por feed
da mesma forma.

Depois de uma execução bem-sucedida do agente (a CLI do agente de código realmente executou), o Curupira armazena
a impressão digital da fonte concluída mais uma próxima ação explícita em `state_db_path`. Um snapshot
concluído e inalterado é ignorado entre ciclos de dispatch. As impressões digitais usam o SHA do head, o flag de draft,
o título e o corpo — não a mergeability, o status de merge-state nem as conclusões dos checks — então
transições de checks ou de conflitos, por si só, não readmitem o trabalho. Um head, flag de draft,
título ou corpo alterado pode ser admitido novamente. Se a própria verificação de conclusão falhar, o Curupira limpa qualquer registro
concluído desse item para que o próximo ciclo tente verificar de novo em vez de ignorá-lo para sempre.
Snapshots ignorados como obsoletos antes de o agente iniciar não são registrados como concluídos.

Os esgotamentos finitos com `run --size N` admitem no máximo `N` tarefas após a revalidação. As sessões recuperadas
contam para `N`; os candidatos descartados durante a revalidação não.

`max_active_tasks` limita os agentes concorrentes (slots de worker). Quando uma tarefa termina, o seu slot é
reabastecido imediatamente pela próxima consulta. As tarefas que compartilham um checkout base serializam o clone
e a preparação do worktree, mas seus agentes rodam em paralelo. Uma tarefa que falha não é repetida dentro
da mesma invocação de `run`; ela é retomada pela próxima.
As automações de cron unem os ticks atrasados em uma única ocorrência pendente e nunca rodam
concorrentemente consigo mesmas. `schedule` usa cinco campos de cron; `timezone` é uma zona IANA (padrão UTC),
e `start_date`/`end_date` opcionais definem uma janela inclusiva. Sem `start_date`, a
janela começa quando a automação é registrada pela primeira vez. `task_timeout_minutes` (padrão 20) é
o prazo para uma execução do agente de código e seu script de setup opcional.

O estado é armazenado em `state_db_path` (padrão `~/.curupira/state.sqlite3`), o lock de dispatch
em `~/.curupira/dispatch.lock` e os logs em `~/.curupira/logs`. Um banco incompatível
causa um erro em vez de uma exclusão automática. Somente um processo `run` ou `tui` pode fazer dispatch
por vez.

## Telemetria

Defina `settings.otlp_endpoint` como um endpoint de traces OTLP/HTTP (por exemplo,
`http://localhost:4318/v1/traces`) para exportar um span por tarefa despachada. Se omitido, nenhuma
telemetria é exportada.
