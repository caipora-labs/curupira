# Primeiros passos

Esta página leva cerca de cinco minutos. Ao final, o Curupira observa um repositório e entrega
toda issue com a label `agent-ready` ao Claude Code. Troque o agente ou a label pelos seus.

Você precisa do [Git](https://git-scm.com/), da [GitHub CLI](https://cli.github.com/) (`gh`) e
de uma CLI de agente de código em que você já esteja logado. A [Instalação](installation.md) cobre
todas as plataformas e opções.

## 1. Instale e faça login

=== "uv"

    ```sh
    uv tool install curupira
    gh auth login
    ```

=== "pip"

    ```sh
    pip install curupira
    gh auth login
    ```

=== "npm"

    ```sh
    npm install -g @caipora-labs/curupira
    gh auth login
    ```

O conector do GitHub é um [plugin](plugins.md) que o Curupira inicia via `uvx`, então você
também precisa do [uv](https://docs.astral.sh/uv/) no `PATH`. Nada mais é instalado antes.

## 2. Escreva `~/.curupira/settings.toml`

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"   # (1)!

[agents.defaults]
profile = "claude"
timezone = "UTC"

[agents.profiles.claude]
provider = "claude"                           # (2)!

[plugins.plugins-py]                          # (3)!
type = "uvx"
args = ["--from", "curupira-plugins", "curupira-plugins"]

[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"     # (4)!
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
prompt = """
Resolve issue #${issue_number}: ${issue_title}

${issue_body}
"""
```

1.  Onde o agente trabalha. O Curupira o clona uma vez e dá a cada tarefa o seu próprio worktree.
2.  Qualquer [agente suportado](providers.md): `codex`, `gemini`, `opencode` e outros.
3.  Registra o conector do GitHub sob o alias `plugins-py`. Os outros conectores são
    registrados da mesma forma.
4.  `<alias>/<trigger>`: o trigger de issues do conector registrado acima. `repo` e
    `labels` são os filtros dele, e `${issue_number}` e os outros campos preenchem o prompt.

## 3. Verifique, visualize, execute

```sh
curupira validate      # o arquivo está correto?
curupira run --dry-run # qual tarefa rodaria, e o prompt exato que o agente recebe
curupira run --watch   # continua consultando e executa as tarefas conforme aparecem
```

!!! tip "Pode repetir sem medo"
    `--dry-run` não clona nada e não inicia nenhum agente. Use-o enquanto ajusta os filtros e o
    prompt.

## Próximos passos

- [Como funciona](concepts.md): o que acontece entre a issue e o agente.
- [Escrevendo prompts](prompts.md): condições, loops e todos os campos que você pode usar.
- [Receitas](recipes.md): revisões de pull requests, Dependabot, colunas de board e cron.
- [Executando o Curupira](operations.md): saída, códigos de saída e sessões.
