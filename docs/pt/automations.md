# Referência de automações

`curu` é o alias curto de `curupira`; ambos executam os mesmos comandos. Esta página é o
mapa para quem está começando com as automações do Curupira: quais triggers existem, um
exemplo mínimo em TOML para cada um, quais placeholders de prompt estão disponíveis e os
primeiros comandos a executar. Os detalhes de cada campo ficam nos guias específicos e em
[Configuração](configuration.md); esta página resume e aponta para eles.

Uma **automação** é uma tabela `[automations.<name>]`. Ela observa uma única fonte
(`trigger_type`), aponta para um repositório Git `[repositories.<alias>]` e carrega um
template de `prompt` para uma CLI de agente de código. Todas as automações compartilham o
mesmo pipeline de descoberta, agendamento e execução.

## Visão geral dos triggers { #trigger-overview }

{{ triggers_table("pt") }}

Os conectores registrados em `[plugins.<alias>]` adicionam mais tipos de trigger, veja
[Plugins e conectores](plugins.md). `curu plugins list` mostra todos os tipos disponíveis e seus
campos de prompt.

## Segurança: o texto das tarefas não é confiável { #security-task-text-is-untrusted }

Títulos e corpos de issues e pull requests do GitHub são entrada não confiável. O Curupira
os coloca no prompt do agente de código (`${issue_title}`, `${issue_body}`,
`${pull_request_title}`, `${pull_request_body}`, `${item_body}`). Um autor hostil pode tentar manipular o agente. Restrinja o que chega ao
agente com `labels`, `author` ou `assignee`. Revise o que o perfil do agente tem permissão
para executar no repositório. Só execute automações em repositórios nos quais você confia em
todas as pessoas que podem escrever texto.

## Primeiros passos { #first-use-path }

1. [Instale o Curupira](installation.md) e apenas as CLIs externas de que suas automações
   precisam (por exemplo, `gh`), além da CLI do agente de código
   do seu perfil:

   ```bash
   npm install -g @caipora/curupira
   # ou: uv tool install curupira
   ```

2. Copie um arquivo de configurações mínimo (ou comece de `curupira.example.toml`) e valide
   sem chamar CLIs externas nem gravar estado:

   ```bash
   curupira --config path/to/settings.toml validate
   ```

3. Faça uma prévia de uma tarefa correspondente, sem clonar um repositório nem iniciar um
   agente:

   ```bash
   curupira --config path/to/settings.toml run --dry-run
   ```

4. Execute uma vez todas as tarefas atualmente disponíveis (adicione `--size N` para limitar)
   ou continue consultando com `--watch`:

   ```bash
   curupira --config path/to/settings.toml run
   curupira --config path/to/settings.toml run --size 1
   curupira --config path/to/settings.toml run --watch
   ```

`--dry-run` não pode ser combinado com `--watch` nem com `--size`. `--size` só vale quando
você executa as tarefas uma vez (não com `--watch`). Os detalhes operacionais e os códigos de
saída estão em [Operação](operations.md).

Cada exemplo abaixo repete `[agents.defaults]` e `[agents.profiles.opencode]` para que
seja válido sozinho. No exemplo de cron, `timezone = "UTC"` é o fuso horário usado para
avaliar o agendamento.

## Issues do GitHub { #github-issues }

Encontra issues usando os filtros que você define no TOML. Requer a
[GitHub CLI](https://cli.github.com/) (`gh auth login`). Guia completo:
[Fontes de tarefas do GitHub](github.md).

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "opencode"

[agents.profiles.opencode]
provider = "opencode"

[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
linked_pull_request = false
prompt = "Resolve issue ${issue_number}: ${issue_title}\n\n${issue_body}"
```

**Placeholders:** `${repository}` e `${automation}` vindos do host, mais as chaves
que este trigger retorna, incluindo `${repo}`, `${issue_number}`, `${issue_title}`,
`${issue_body}` e `${issue_url}`.

**O que o agente recebe:** a string `prompt` renderizada, com o agente trabalhando no
repositório Git indicado por `repository`. `${repo}` é uma chave retornada pelo trigger do GitHub;
`${repository}` é a identidade do forge derivada do remote Git.

## Pull requests do GitHub { #github-pull-requests }

Encontra pull requests usando os filtros que você define no TOML (incluindo verificações
opcionais de merge após a listagem). Requer `gh`. Guia completo: [Fontes de tarefas do GitHub](github.md).

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "opencode"

[agents.profiles.opencode]
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

**Placeholders:** `${repository}` e `${automation}` vindos do host, mais as chaves
que este trigger retorna, incluindo `${pull_request_number}`,
`${pull_request_title}`, `${pull_request_body}`, `${pull_request_url}`,
`${pull_request_is_draft}`, `${pull_request_head_ref}` e
`${pull_request_base_ref}`.

**O que o agente recebe:** o prompt de revisão renderizado no repositório Git indicado por
`repository`. Valores booleanos são renderizados como `true` / `false`. Um campo cujo valor é `None`
é renderizado como `null`. Um `${key}` que o resultado não contém é deixado inalterado.

## Cron { #cron }

Executa em um agendamento local que você define com um `schedule` de cinco campos. Nenhuma
CLI externa de board ou de issue tracker é necessária. As opções de agendamento (fuso
horário, datas de início/fim) estão em
[Configuração](configuration.md#scheduling-and-state).

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "opencode"
timezone = "UTC"

[agents.profiles.opencode]
provider = "opencode"

[automations.weekly-maintenance]
trigger_type = "cron"
repository = "api"
schedule = "0 9 * * 1"
prompt = "Perform weekly maintenance for ${repository} (${automation})."
```

**Placeholders:** apenas `${repository}` e `${automation}`. O cron não retorna
pares do trigger. O `timezone` opcional sobrescreve `[agents.defaults].timezone`;
`start_date` / `end_date` opcionais delimitam a janela inclusiva.

**O que o agente recebe:** o prompt de manutenção renderizado no repositório Git indicado
por `repository` quando o agendamento vence. Execuções atrasadas são mescladas em uma única
execução pendente, e a mesma automação nunca roda duas vezes ao mesmo tempo.

## Erros comuns de configuração { #common-configuration-errors }

| Sintoma | Causa provável | Correção |
| --- | --- | --- |
| `unknown trigger type: …` | Erro de digitação, ou o plugin não está registrado | Confira o `trigger_type` com `curu plugins list` |
| Erros de alias de repositório / repositório ausente | `repository` não corresponde a uma chave `[repositories.<alias>]` | Alinhe o alias e garanta que `remote` seja uma URL Git completa |
| Placeholder deixado inalterado no prompt | `${name}` não é uma variável do host e o trigger não retornou essa chave | Use uma chave que o trigger retorna; veja a [Referência de campos do prompt](prompt-fields.md). O `validate` sugere a chave mais próxima |
| `prompt uses unknown field(s)` no `validate` | Um `{{ name }}` (ou um `${name}` que parece um erro de digitação) não é uma chave deste trigger | Corrija o nome; a mensagem lista os campos disponíveis |
| Erro de template do prompt com número de linha | Sintaxe Jinja inválida, por exemplo um bloco `if` sem o `endif` | Corrija a linha indicada. Para imprimir chaves duplas literais, use um bloco `raw`, veja [Escrevendo prompts](prompts.md#values-are-text) |
| `Required executable not found: gh` | CLI ausente do `PATH` | Instale e autentique a CLI desse trigger |
| `schedule must be a valid five-field cron expression` | Cron de seis campos ou expressão inválida | Use cinco campos (`minute hour day-of-month month day-of-week`) |
| `repo must use the owner/repository format` | `repo` do GitHub não está no formato `owner/name` | Use `acme/api`, não uma URL |
| No tasks scheduled | Os filtros não encontram nada | Amplie ou remova os filtros de labels / branch; ciclos vazios não são um erro |
| `validate` termina com `2` | Estrutura do TOML, chaves de configuração desconhecidas ou erros de prompt | Leia a mensagem de validação; os modelos rejeitam chaves desconhecidas |

`curu validate` verifica a estrutura do TOML, a configuração dos triggers e o prompt (sintaxe e nomes de campos)
sem chamar APIs externas. `curu run` e `curu run --watch` exigem que as CLIs dos seus triggers
e a CLI do agente escolhido estejam instaladas e autenticadas.
