# Gemini CLI

O Curupira executa a [Gemini CLI](https://github.com/google-gemini/gemini-cli) de forma não interativa
com saída JSON em streaming:

```text
gemini --output-format stream-json [options] --prompt=<prompt>
```

## Instale e faça login { #install }

A Gemini CLI precisa do Node.js 20 ou mais recente.

```sh
npm install -g @google/gemini-cli
gemini   # faça login uma vez com a sua conta Google
```

Você também pode definir `GEMINI_API_KEY` ou configurar o Vertex AI. A Gemini CLI cuida da autenticação;
o Curupira nunca lê nem armazena credenciais.

## Opções do perfil { #options }

| Opção | Argumento nativo | Observações |
| --- | --- | --- |
| `model` | `--model <model>` | `auto` deixa o Gemini escolher. |
| `approval_mode` | `--approval-mode <mode>` | `default`, `auto_edit`, `yolo` ou `plan`. Sem valor, mantém a política do Gemini. |
| `skip_trust = true` | `--skip-trust` | Pula a verificação de confiança da pasta. |
| `agent` | — | Não suportado; rejeitado. |
| `effort` | — | Não suportado; rejeitado. |

!!! warning "`yolo` aprova tudo"
    `approval_mode = "yolo"` desativa os pedidos de aprovação. O Curupira passa
    `--approval-mode yolo` em vez da flag obsoleta `--yolo`.

O prompt é passado como `--prompt=<prompt>`, então um prompt que começa com `-` continua sendo texto.

## Exemplo { #example }

```toml
[agents.profiles.gemini]
provider = "gemini"
model = "auto"
approval_mode = "auto_edit"
```

## Sessões { #sessions }

O id de sessão vem do evento `init` do Gemini e é salvo com a tarefa. Uma
tarefa interrompida é retomada com `--resume <session_id>`.
