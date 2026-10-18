# Cursor

O Curupira executa a [Cursor CLI](https://cursor.com/cli) (o comando `agent`) em modo print
com saída JSON em streaming:

```text
agent --print --output-format stream-json [options] -- <prompt>
```

## Instale e faça login { #install }

```sh
curl https://cursor.com/install -fsS | bash
agent login
```

A Cursor CLI cuida da autenticação. O Curupira nunca lê nem armazena credenciais.

## Opções do perfil { #options }

| Opção | Argumento nativo | Observações |
| --- | --- | --- |
| `model` | `--model <model>` | `auto` deixa o Cursor escolher. |
| `agent` | `--mode <mode>` | `agent`, `ask` ou `plan`. |
| `force = true` | `--force` | Permite comandos sem confirmação. |
| `trust = true` | `--trust` | Confia no workspace nesta execução. |
| `effort` | — | Não suportado; rejeitado. |

## Exemplo { #example }

```toml
[agents.profiles.cursor]
provider = "cursor"
model = "auto"
agent = "agent"
force = true
```

## Sessões { #sessions }

O id de sessão do stream JSON é salvo com a tarefa. Uma tarefa interrompida é retomada
com `--resume <session_id>`.
