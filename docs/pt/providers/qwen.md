# Qwen Code

Instale o Qwen Code com Node.js 22 ou superior:

```bash
npm install -g @qwen-code/qwen-code@latest
```

O Curupira executa `qwen --output-format stream-json --prompt=<message>`. Ele retoma uma
sessão conhecida com `--resume <session_id>`. O Qwen Code é responsável pela autenticação; o Curupira não
lida com credenciais de providers.

| Opção do profile | Argumento nativo |
| --- | --- |
| `model` | `--model` opcional |
| `approval_mode` | `--approval-mode` opcional (`plan`, `default`, `auto-edit`, `auto` ou `yolo`) |
| `max_session_turns` | `--max-session-turns` opcional (inteiro ≥ 1) |
| `agent` | Não suportado; rejeitado |
| `effort` | Não suportado; rejeitado |

`approval_mode = "yolo"` habilita a aprovação automática. A documentação do Qwen Code alerta
que o modo YOLO “não habilita um sandbox”.

As opções `--max-wall-time` e `--max-tool-calls` não são expostas; o timeout de tarefa do Curupira
limita cada execução.

::: curupira.agents.qwen.QwenCodeCliProfile
