# Codex

O Curupira executa a [Codex CLI](https://github.com/openai/codex) de forma não interativa com eventos
JSON:

```text
codex exec [options] --json -- <prompt>
```

## Instale e faça login { #install }

```sh
npm install -g @openai/codex
codex login
```

O Codex cuida da autenticação (uma conta ChatGPT ou uma chave de API). O Curupira nunca lê nem
armazena credenciais.

## Opções do perfil { #options }

| Opção | Argumento nativo | Observações |
| --- | --- | --- |
| `model` | `--model <model>` | |
| `agent` | `--profile <name>` | Um perfil do seu `config.toml` do Codex. |
| `effort` | `--config model_reasoning_effort="<level>"` | Por exemplo `low`, `medium`, `high`, `xhigh`. A disponibilidade depende do modelo. |
| `sandbox` | `--sandbox <mode>` | Por exemplo `workspace-write`. Sem valor, mantém a política do Codex. |
| `auto_review = true` | `--config approval_policy="on-request"` e `--config approvals_reviewer="auto_review"` | Deixa o Codex revisar os próprios pedidos de aprovação. |

Opções sem valor não adicionam argumento.

## Exemplo { #example }

```toml
[agents.profiles.codex]
provider = "codex"
model = "gpt-5-codex"
effort = "high"
sandbox = "workspace-write"
```

## Sessões { #sessions }

O id da thread nos eventos JSON é salvo com a tarefa. Uma tarefa interrompida é retomada
com `codex exec resume <thread_id>`.
