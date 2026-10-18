# Qwen Code

O Curupira executa o [Qwen Code](https://github.com/QwenLM/qwen-code) de forma não interativa com
saída JSON em streaming:

```text
qwen --output-format stream-json [options] --prompt=<prompt>
```

## Instale e faça login { #install }

O Qwen Code precisa do Node.js 22 ou mais recente.

```sh
npm install -g @qwen-code/qwen-code@latest
qwen   # faça login uma vez
```

O Qwen Code cuida da autenticação. O Curupira nunca lê nem armazena credenciais.

## Opções do perfil { #options }

| Opção | Argumento nativo | Observações |
| --- | --- | --- |
| `model` | `--model <model>` | |
| `approval_mode` | `--approval-mode <mode>` | `plan`, `default`, `auto-edit`, `auto` ou `yolo`. |
| `max_session_turns` | `--max-session-turns <n>` | Um inteiro de pelo menos `1`. |
| `agent` | — | Não suportado; rejeitado. |
| `effort` | — | Não suportado; rejeitado. |

!!! warning "`yolo` não é um sandbox"
    `approval_mode = "yolo"` aprova todas as ações automaticamente. A documentação do Qwen Code
    avisa que ele "não ativa um sandbox".

`--max-wall-time` e `--max-tool-calls` não são expostos; o `task_timeout_minutes` do Curupira
limita cada execução.

## Exemplo { #example }

```toml
[agents.profiles.qwen]
provider = "qwen"
approval_mode = "auto-edit"
max_session_turns = 40
```

## Sessões { #sessions }

O id de sessão do stream JSON é salvo com a tarefa. Uma tarefa interrompida é retomada
com `--resume <session_id>`.
