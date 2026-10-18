# Kilo CLI

O Curupira executa a [Kilo CLI](https://kilocode.ai/cli) no modo `run` com saída JSON:

```text
kilo run --format json [options] -- <prompt>
```

## Instale e faça login { #install }

```sh
npm install -g @kilocode/cli
kilo auth login
```

O Kilo e as suas integrações com providers cuidam da autenticação. O Curupira nunca lê nem armazena
credenciais.

## Opções do perfil { #options }

| Opção | Argumento nativo | Observações |
| --- | --- | --- |
| `model` | `--model <provider/model>` | Precisa usar a forma `provider/model`; qualquer outra coisa é um erro de configuração. |
| `agent` | `--agent <agent>` | Um agente Kilo existente. |
| `effort` | `--variant <variant>` | Variante de raciocínio específica do provider, como `high`, `max` ou `minimal`. |
| `auto_approve = true` | `--auto` | Aprova as permissões que não são negadas explicitamente. Use com cuidado. |

O `--thinking` do Kilo apenas exibe os blocos de raciocínio, então ele não é usado para `effort`.
Sem `auto_approve`, o Kilo rejeita pedidos de permissão em execuções headless em vez de
esperar por uma resposta.

## Exemplo { #example }

```toml
[agents.profiles.kilo]
provider = "kilo"
model = "anthropic/claude-sonnet-4"
effort = "high"
```

## Sessões { #sessions }

Todo registro JSON traz o id de sessão, que é salvo com a tarefa. Uma tarefa
interrompida é retomada com `--session <session_id>`.
