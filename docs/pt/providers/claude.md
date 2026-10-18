# Claude Code

O Curupira executa o [Claude Code](https://docs.anthropic.com/en/docs/claude-code) em modo print
com saída JSON em streaming:

```text
claude -p --output-format stream-json --verbose [options] -- <prompt>
```

## Instale e faça login { #install }

```sh
npm install -g @anthropic-ai/claude-code
claude   # faça login uma vez, de forma interativa
```

O Claude Code cuida da autenticação (uma conta Anthropic ou `ANTHROPIC_API_KEY`). O Curupira
nunca lê nem armazena credenciais.

## Opções do perfil { #options }

| Opção | Argumento nativo | Observações |
| --- | --- | --- |
| `model` | `--model <model>` | Um alias como `sonnet` ou um id de modelo completo. |
| `agent` | `--agent <agent>` | Um agente personalizado definido no Claude Code. |
| `effort` | `--effort <level>` | Nível de esforço de raciocínio. |
| `permission_mode` | `--permission-mode <mode>` | Por exemplo `acceptEdits` ou `plan`. Sem valor, mantém o padrão do Claude Code. |
| `permission_prompts` | `--permission-prompts <value>` | Repassado sem alterações. |

Opções sem valor não adicionam argumento. O prompt sempre vem depois de `--`, então um prompt que começa
com `-` não é lido como flag.

## Exemplo { #example }

```toml
[agents.profiles.claude]
provider = "claude"
model = "sonnet"
permission_mode = "acceptEdits"
```

## Sessões { #sessions }

O id de sessão do stream JSON é salvo com a tarefa. Uma tarefa interrompida é retomada
com `--resume <session_id>`.
