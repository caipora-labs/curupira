# Curupira

O Curupira executa automações na sua máquina. Ele observa uma fonte de trabalho (issues do GitHub, pull
requests, uma coluna de um board do GitHub Projects ou um agendamento cron) e entrega cada item para uma
CLI de agente de código que você já usa, como Claude Code, Codex, Gemini ou OpenCode. Cada
tarefa roda em seu próprio worktree do Git, então o seu checkout nunca é tocado.

Tudo é configurado em um único arquivo TOML, `~/.curupira/settings.toml`.

## Início rápido (cerca de 5 minutos) { #quick-start }

Você precisa do [Git](https://git-scm.com/), da [GitHub CLI](https://cli.github.com/) (`gh`) e de uma
CLI de agente de código. Os detalhes estão em [Instalação](installation.md).

**1. Instale e faça login**

```sh
uv tool install 'curupira[github]'
gh auth login
```

**2. Crie `~/.curupira/settings.toml`**

Esta configuração resolve issues que têm o label `agent-ready`:

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"   # onde o agente trabalha

[agents.defaults]
profile = "claude"
timezone = "UTC"

[agents.profiles.claude]
provider = "claude"

[plugins.plugins-py]                          # os triggers oficiais do GitHub
type = "uvx"
args = ["--from", "curupira-plugins", "curupira-plugins"]

[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"
repository = "api"
repo = "acme/api"                             # o repositório do GitHub a observar
labels = ["agent-ready"]
prompt = """
Resolve issue #${issue_number}: ${issue_title}

${issue_body}
"""
```

**3. Valide, visualize e execute**

```sh
curupira validate      # o arquivo está correto?
curupira run --dry-run # qual tarefa rodaria e o prompt exato que o agente recebe
curupira run --watch   # continua consultando e executa as tarefas conforme aparecem
```

O `--dry-run` não clona nada e não inicia nenhum agente, então é seguro repeti-lo enquanto você ajusta
os filtros e o prompt.

## Para onde ir em seguida

| Eu quero... | Leia |
| --- | --- |
| Instalar o Curupira e as CLIs dos agentes | [Instalação](installation.md) |
| Entender cada configuração do arquivo | [Configuração](configuration.md) |
| Escolher um trigger e ver um exemplo mínimo | [Automações](automations.md) |
| Filtrar issues e pull requests | [Issues e pull requests do GitHub](github.md) |
| Trabalhar a partir de uma coluna de um board | [GitHub Projects](github-projects.md) |
| Escrever um prompt mais inteligente (condições, laços) | [Escrevendo prompts](prompts.md) |
| Ver todos os campos que um prompt pode usar | [Referência de campos do prompt](prompt-fields.md) |
| Copiar uma configuração que funciona | [Receitas](recipes.md) |
| Escolher ou ajustar o agente de código | [Providers e agentes](providers.md) |
| Usar no dia a dia, ler logs, corrigir erros | [Operação](operations.md) |
