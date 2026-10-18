# Desenvolver extensões

Uma extensão é uma **fonte de tarefas**: um pequeno programa que diz ao Curupira qual trabalho existe.
Os [conectores](plugins.md) (GitHub hoje, Monday.com e Azure DevOps em desenvolvimento) são extensões, e você
pode escrever os seus para Jira, Linear, uma fila em banco de dados ou qualquer outra coisa que consiga
produzir um item por vez.

As extensões rodam como **processos separados**. O Curupira as inicia com `uvx` ou `npx` e
conversa com elas por stdin e stdout com um pequeno
[protocolo JSON-RPC](extensions-protocol.md). Elas nunca rodam dentro do processo do Curupira,
e não há FFI envolvido.

<div class="grid cards" markdown>

-   :material-language-python:{ .lg } **SDK Python**

    ---

    `curupira-sdk`: decore uma função e retorne um objeto. Apenas a biblioteca padrão, Pydantic opcional.

    [Escreva uma extensão em Python](extensions-python.md)

-   :material-language-javascript:{ .lg } **SDK JavaScript e TypeScript**

    ---

    `@caipora-labs/curupira-sdk`: `defineTriggers` e um `bin` do npm, iniciado com `npx`.

    [Escreva uma extensão em Node.js](extensions-javascript.md)

-   :material-file-document-outline:{ .lg } **Manifesto e protocolo**

    ---

    Framing, métodos, resultados, códigos de erro e o manifesto `curupira-extension.toml`.

    [Leia a referência](extensions-protocol.md)

</div>

## O que uma extensão faz { #responsibilities }

| Uma extensão... | O Curupira (o host)... |
| --- | --- |
| Declara os seus triggers e as configurações que cada um aceita | Lê o TOML e passa as configurações de cada automação |
| Valida essas configurações | Relata os erros de validação no `curupira validate` |
| Retorna o **próximo item** como uma lista plana de pares chave/valor, ou nada | Deduplica, agenda e limita a concorrência |
| É avisada quando uma tarefa começa e quando termina | Clona, cria worktrees, executa o `setup_script` |
| Escreve logs no stderr | Renderiza o prompt e inicia o agente de código |

As extensões não devem escolher um agente de código, montar linhas de comando de agentes, clonar repositórios
nem gerenciar worktrees. Os agentes de código são embutidos no host; suportar um novo agente é uma
mudança no próprio Curupira.

## Registre uma extensão { #register }

Toda extensão é registrada no `settings.toml` sob um alias de sua escolha, com o
launcher e os argumentos dele. As automações então endereçam um trigger como `<alias>/<trigger>`.

=== "Python (uvx)"

    ```toml
    [plugins.acme]
    type = "uvx"
    args = ["--from", "acme-curupira==1.2.0", "acme-curupira"]
    tools = ["*"]

    [automations.triage]
    trigger_type = "acme/tickets"
    repository = "api"
    prompt = "Triage ${title}"
    ```

=== "Node.js (npx)"

    ```toml
    [plugins.acme]
    type = "npx"
    args = ["--yes", "@acme/curupira-ext@1.2.0"]
    tools = ["*"]

    [automations.triage]
    trigger_type = "acme/tickets"
    repository = "api"
    prompt = "Triage ${title}"
    ```

Os `args` são passados como argumentos separados, nunca por um shell. Fixe uma versão para que todas as
máquinas executem o mesmo código. `tools` mantém apenas os triggers correspondentes (`github-*`) ou os
remove (`!github-project-*`).

## Inspecione os plugins { #manage }

`curupira plugins` lista os triggers que você pode usar e as configurações que cada um aceita:

```sh
curupira plugins list
curupira plugins info curupira-plugins
```

`plugins list` também mostra o cron embutido e os providers de agentes de código embutidos (rotulados
`agent:<name>` com origem `built-in`). Listar lê os manifestos `curupira-extension.toml` e
**nunca executa código de extensões**.

### Requisitos de execução { #runtime-requirements }

| Origem | Precisa no `PATH` |
| --- | --- |
| Plugins `type = "uvx"` | `uvx` (do [uv](https://docs.astral.sh/uv/)) |
| Plugins `type = "npx"` | `npx` (Node.js 20+) |
| Cron e agentes de código embutidos | as CLIs de agente que você configurar, mais o `git` |

Se faltar um launcher, `curupira validate` diz qual.

## Segurança { #security }

Extensões de terceiros rodam com os privilégios do seu usuário. Um subprocesso não é um sandbox.
Instale apenas pacotes em que você confia e fixe as versões deles. O Curupira nunca instala pacotes
ao listar os plugins.

O texto que uma extensão retorna geralmente vem de pessoas de fora da sua equipe (títulos de issues,
comentários). Ele acaba em um prompt; leia
[o texto das tarefas não é confiável](github.md#security) antes de automatizar fontes públicas.
