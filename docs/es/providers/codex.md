# Codex

Ejecuta `codex exec --json`; reanuda con `codex exec resume <thread_id>`. El esfuerzo se pasa como `--config model_reasoning_effort=<level>`. Los niveles documentados incluyen `low`, `medium`, `high`, `xhigh`, `max` y `ultra`; la disponibilidad depende del modelo y de la versión de la CLI.

| Opción | Argumento nativo |
| --- | --- |
| `agent` | Perfil de configuración mediante `--profile` |
| `model` | `--model` opcional |
| `effort` | `model_reasoning_effort` mediante `--config` |
