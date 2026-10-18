# Plugins e conectores

Um **plugin** é um programa que informa ao Curupira que trabalho existe. Um **conector** é um
plugin para uma ferramenta que você já usa, como o GitHub. O Curupira inicia o plugin, pede o
próximo item e entrega esse item ao seu agente de código em um worktree Git próprio.

Os conectores não estão presos a um único serviço. O GitHub é o primeiro a ser lançado, o
Monday.com e o Azure DevOps estão em desenvolvimento, e você pode
[escrever o seu](extensions.md).

## Conectores { #catalog }

<div class="grid cards" markdown>

-   :material-github:{ .lg } **GitHub** <span class="cp-status cp-status--live">Disponível</span>

    ---

    Issues, pull requests e colunas de boards do Projects, por meio da CLI `gh`. Nenhum token
    vai nas suas configurações.

    [Issues e pull requests do GitHub](github.md) · [Projects](github-projects.md)

-   :material-view-dashboard-outline:{ .lg } **Monday.com** <span class="cp-status cp-status--dev">Em desenvolvimento</span>

    ---

    Itens dos seus boards do Monday.com como tarefas para o agente.

    Ainda não foi lançado.

-   :material-microsoft-azure-devops:{ .lg } **Azure DevOps** <span class="cp-status cp-status--dev">Em desenvolvimento</span>

    ---

    Work items do Azure DevOps como tarefas para o agente.

    Ainda não foi lançado.

-   :material-puzzle-plus-outline:{ .lg } **O seu próprio** <span class="cp-status cp-status--live">Disponível</span>

    ---

    Um conector para Jira, Linear, uma fila em banco de dados ou qualquer coisa que consiga
    devolver um item por vez.

    [Desenvolver extensões](extensions.md)

</div>

Todo conector funciona do mesmo jeito para você: registre-o uma vez e aponte as automações
para os seus triggers. Só mudam os nomes dos triggers e os seus filtros.

Os triggers que existem hoje:

| Trigger | Fonte | Requer |
| --- | --- | --- |
| [`plugins-py/github-issues`](github.md#minimal-issue-automation) | Issues do GitHub | `gh auth login` |
| [`plugins-py/github-pull-requests`](github.md) | Pull requests do GitHub | `gh auth login` |
| [`plugins-py/github-project-items`](github-projects.md) | Colunas de boards do GitHub Projects | `gh` com o escopo `read:project` |
| [`cron`](automations.md#cron) | Uma agenda local, embutida no Curupira | Nada |

## Registre um conector { #register }

Um plugin é registrado sob um alias que você escolhe, junto com o launcher que o inicia. As
automações então endereçam um trigger como `<alias>/<trigger>`.

```toml
[plugins.plugins-py]                                  # (1)!
type = "uvx"
args = ["--from", "curupira-plugins", "curupira-plugins"]

[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"             # (2)!
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
prompt = "Resolve issue #${issue_number}: ${issue_title}"
```

1.  O alias é você quem escolhe. `plugins-py` é a convenção usada nesta documentação para o
    conector oficial do GitHub.
2.  `<alias>/<trigger>`: o trigger vem do plugin registrado acima. As demais chaves são os
    filtros desse trigger.

O pacote roda via `uvx`, então você precisa do [uv](https://docs.astral.sh/uv/) no `PATH`.
Plugins escritos para Node.js rodam via `npx`; veja
[Registre uma extensão](extensions.md#register).

=== "Fixar uma versão"

    ```toml
    [plugins.plugins-py]
    type = "uvx"
    args = ["--from", "curupira-plugins==0.3.0", "curupira-plugins"]
    ```

    Assim, todas as máquinas executam a mesma versão do plugin.

=== "Manter alguns triggers"

    ```toml
    [plugins.plugins-py]
    type = "uvx"
    args = ["--from", "curupira-plugins", "curupira-plugins"]
    tools = ["github-*", "!github-project-*"]
    ```

    `tools` mantém os triggers correspondentes; um padrão com `!` os remove.

## Use o conector do GitHub { #github }

Faça login uma vez. O conector chama o `gh` com a sua conta, então enxerga exatamente os
repositórios e boards que você enxerga.

```sh
gh auth login
gh auth refresh -s read:project   # apenas para colunas de boards do Projects
```

Veja [Escopos do token](github.md#prerequisites) para mais detalhes e escolha um trigger:

<div class="grid cards" markdown>

-   :material-alert-circle-outline:{ .lg } **Issues**

    ---

    Labels, responsáveis, milestones, pull requests vinculados e busca livre.

    [`github-issues`](github.md#minimal-issue-automation)

-   :material-source-pull:{ .lg } **Pull requests**

    ---

    Rascunhos, estado da revisão, status do CI, autores como o Dependabot e possibilidade de merge.

    [`github-pull-requests`](github.md)

-   :material-view-column-outline:{ .lg } **Colunas de boards do Projects**

    ---

    Cards em uma coluna de um GitHub Project, com os seus campos personalizados.

    [`github-project-items`](github-projects.md)

-   :material-book-open-variant:{ .lg } **Receitas**

    ---

    Configurações completas para copiar: revisões, Dependabot, feedback e boards.

    [Receitas](recipes.md)

</div>
