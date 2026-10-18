# Agentes de código

O Curupira não traz um modelo nem chama uma API de LLM. Ele inicia a CLI de agente de código que você
já usa, em modo não interativo, dentro do worktree da tarefa. O seu login, o acesso aos modelos
e as configurações do agente continuam nessa CLI.

## Agentes suportados { #supported }

{{ agents_table("pt") }}

Todos os adaptadores são embutidos no Curupira. Adicionar um agente é uma mudança no próprio Curupira, não
um plugin.

## Perfis { #profiles }

Um perfil é uma forma nomeada de executar um agente. Defina quantos precisar e escolha um por
automação:

```toml
[agents.defaults]
profile = "claude"            # usado quando uma automação não define um perfil
timezone = "UTC"

[agents.profiles.claude]
provider = "claude"
model = "sonnet"

[agents.profiles.codex-high]
provider = "codex"
effort = "high"

[automations.review-ready-prs]
trigger_type = "plugins-py/github-pull-requests"
repository = "api"
repo = "acme/api"
profile = "codex-high"        # esta automação usa o Codex
prompt = "Review pull request #${pr_number}."
```

`model`, `agent` e `effort` são opcionais e significam a mesma coisa em todos os lugares; a página de cada
agente mostra a flag nativa em que eles se transformam. Uma opção que você omite não adiciona nenhum argumento,
então a CLI mantém o próprio padrão. Uma opção que o agente não suporta é um erro de
configuração, e não é ignorada em silêncio.

## Permissões { #permissions }

Execuções sem supervisão não conseguem responder a pedidos de permissão. Cada CLI tem os próprios controles, e
o Curupira só passa os que você definir:

| Agente | Opções |
| --- | --- |
| [Claude Code](providers/claude.md) | `permission_mode`, `permission_prompts` |
| [Codex](providers/codex.md) | `sandbox`, `auto_review` |
| [Cursor](providers/cursor.md) | `force`, `trust` |
| [Gemini CLI](providers/gemini.md) | `approval_mode`, `skip_trust` |
| [GitHub Copilot CLI](providers/copilot.md) | `allow_all_tools`, `allow_tools`, `deny_tools` |
| [Kilo CLI](providers/kilo.md) e [OpenCode](providers/opencode.md) | `auto_approve` |
| [pi](providers/pi.md) | `tools`, `exclude_tools`, `approve` |
| [Qwen Code](providers/qwen.md) | `approval_mode`, `max_session_turns` |

!!! warning "O texto das tarefas não é confiável"
    O texto de issues e pull requests acaba no prompt. Permissões amplas somadas a um repositório
    público permitem que qualquer pessoa que consiga abrir uma issue direcione o agente. Leia
    [Segurança](github.md#security) antes de afrouxar as permissões.

## Sessões e limites { #sessions }

O Curupira salva o id de sessão de cada agente com a tarefa e a retoma se o processo parar
antes de a tarefa terminar. Toda execução é limitada por `[settings].task_timeout_minutes`
(padrão `20`) e `[settings].max_output_bytes`.
