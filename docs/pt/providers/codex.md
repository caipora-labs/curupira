# Codex

Executa `codex exec --json`; retoma com `codex exec resume <thread_id>`. O effort é passado como `--config model_reasoning_effort=<level>`. Os níveis documentados incluem `low`, `medium`, `high`, `xhigh`, `max` e `ultra`; a disponibilidade depende do model e da versão da CLI.

| Opção | Argumento nativo |
| --- | --- |
| `agent` | Profile de configuração via `--profile` |
| `model` | `--model` opcional |
| `effort` | `model_reasoning_effort` via `--config` |
