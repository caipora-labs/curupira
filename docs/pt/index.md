---
template: home.html
title: Curupira
description: Entregue tarefas do GitHub, boards de projeto e agendamentos cron para a CLI de agente de código que você já usa.
hide:
  - navigation
  - toc
hero:
  eyebrow: Automações locais para agentes de código
  title: Entregue o seu backlog ao agente de código que você já usa
  lead: >-
    O Curupira observa fontes de tarefas por meio de conectores (GitHub hoje, Monday.com e
    Azure DevOps em desenvolvimento) e agendamentos cron, e executa cada tarefa com Claude
    Code, Codex, Gemini ou outra CLI de agente em seu próprio worktree Git. Ele roda na sua
    máquina, a partir de um único arquivo TOML.
  primary:
    text: Comece agora
    href: quick-start/
  secondary:
    text: Como funciona
    href: concepts/
  install_label: Instalar
  trace_label: Exemplo de sessão no terminal
  trace_caption: >-
    Valide o arquivo, veja o prompt exato e continue observando. Cada tarefa concluída
    imprime ok com a sua identidade e nunca é executada duas vezes.
---

<div class="grid cards cp-cols-4" markdown>

-   :material-rocket-launch-outline:{ .lg } **Comece agora**

    ---

    Instale a CLI, escreva uma primeira automação e veja o prompt antes que algo rode.

    [Primeiros passos](quick-start.md) · [Instalação](installation.md)

-   :material-transit-connection-variant:{ .lg } **Orquestrador**

    ---

    Configure repositórios, perfis de agente, automações, prompts e o loop de execução.

    [Configuração](configuration.md) · [Executando o Curupira](operations.md)

-   :material-puzzle-outline:{ .lg } **Plugins e conectores**

    ---

    Fontes de tarefas para o GitHub e mais. Cada conector é um plugin que você registra pelo nome.

    [Visão geral dos plugins](plugins.md) · [Receitas](recipes.md)

-   :material-code-braces:{ .lg } **Desenvolver extensões**

    ---

    Escreva o seu próprio conector em Python ou JavaScript com os SDKs do Curupira.

    [Visão geral das extensões](extensions.md) · [Protocolo](extensions-protocol.md)

</div>

## Conectores { #connectors }

Um conector é um plugin que informa ao Curupira que trabalho existe. Escolha um, registre-o no
`settings.toml` e cada tarefa que ele encontrar vai para o seu agente.

<div class="grid cards cp-cols-4" markdown>

-   :material-github:{ .lg } **GitHub** <span class="cp-status cp-status--live">Disponível</span>

    ---

    Issues, pull requests e colunas de boards do Projects, por meio da CLI `gh`.

    [Conector do GitHub](github.md)

-   :material-view-dashboard-outline:{ .lg } **Monday.com** <span class="cp-status cp-status--dev">Em desenvolvimento</span>

    ---

    Itens dos seus boards do Monday.com como tarefas para o agente.

    [Visão geral dos plugins](plugins.md#catalog)

-   :material-microsoft-azure-devops:{ .lg } **Azure DevOps** <span class="cp-status cp-status--dev">Em desenvolvimento</span>

    ---

    Work items do Azure DevOps como tarefas para o agente.

    [Visão geral dos plugins](plugins.md#catalog)

-   :material-puzzle-plus-outline:{ .lg } **O seu próprio** <span class="cp-status cp-status--live">Disponível</span>

    ---

    Qualquer coisa que consiga devolver um item por vez pode ser um conector.

    [Desenvolver extensões](extensions.md)

</div>

O cron é embutido e não precisa de conector: [agende uma automação](automations.md#cron).

## Funciona com a sua CLI de agente { #agents }

O Curupira inicia cada agente pelo próprio comando não interativo dele, então o seu login,
os seus modelos e as suas configurações continuam onde estão.

<div class="cp-agents" markdown>

- [Claude Code](providers/claude.md)
- [Codex](providers/codex.md)
- [Cursor](providers/cursor.md)
- [Gemini CLI](providers/gemini.md)
- [GitHub Copilot CLI](providers/copilot.md)
- [Kilo CLI](providers/kilo.md)
- [OpenCode](providers/opencode.md)
- [pi](providers/pi.md)
- [Qwen Code](providers/qwen.md)

</div>

## Tarefas comuns { #tasks }

<div class="cp-tasks" markdown>

- [Instalação](installation.md) <span>Instalar o Curupira e as CLIs de agente</span>
- [Como funciona](concepts.md) <span>Acompanhar uma tarefa da fonte até o agente</span>
- [Configuração](configuration.md) <span>Entender cada configuração do arquivo</span>
- [Automações](automations.md) <span>Escolher um trigger e ver um exemplo mínimo</span>
- [Conector do GitHub](github.md) <span>Filtrar issues e pull requests</span>
- [GitHub Projects](github-projects.md) <span>Trabalhar a partir de uma coluna de um board</span>
- [Escrevendo prompts](prompts.md) <span>Usar condições e loops em um prompt</span>
- [Referência de campos do prompt](prompt-fields.md) <span>Ver todos os campos que um prompt pode usar</span>
- [Receitas](recipes.md) <span>Copiar uma configuração que funciona</span>
- [Agentes de código](providers.md) <span>Escolher ou ajustar o agente de código</span>
- [Executando o Curupira](operations.md) <span>Usar no dia a dia e corrigir erros</span>
- [Desenvolver extensões](extensions.md) <span>Escrever o seu próprio conector</span>

</div>
