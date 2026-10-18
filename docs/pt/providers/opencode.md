# OpenCode

O Curupira executa o [OpenCode](https://opencode.ai) no modo `run` com saída JSON, apontado para
o worktree da tarefa:

```text
opencode run --format json --dir <worktree> [options] -- <prompt>
```

## Instale e faça login { #install }

```sh
npm install -g opencode-ai
opencode auth login
```

O OpenCode cuida da autenticação de cada provider de modelos. O Curupira nunca lê nem armazena
credenciais.

## Opções do perfil { #options }

| Opção | Argumento nativo | Observações |
| --- | --- | --- |
| `model` | `--model <provider/model>` | |
| `agent` | `--agent <agent>` | Um agente personalizado do OpenCode. |
| `effort` | `--variant <variant>` | Variante de raciocínio específica do provider. |
| `auto_approve = true` | `--auto` | Aprova as permissões que não são negadas explicitamente. Use com cuidado. |

Cada execução define `OPENCODE_DB` para um banco de dados ao lado do worktree, então tarefas paralelas não
compartilham o estado do OpenCode.

## Exemplo { #example }

```toml
[agents.profiles.opencode]
provider = "opencode"
model = "anthropic/claude-sonnet-4"
agent = "build"
```

## Sessões { #sessions }

O id de sessão dos eventos JSON é salvo com a tarefa. Uma tarefa interrompida é retomada
com `--session <session_id>`.
