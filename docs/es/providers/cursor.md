# Cursor

Ejecuta `agent --print --output-format stream-json`, pasando el modelo con `--model` y el modo con `--mode`. Reanuda con `--resume <session_id>`. El esfuerzo no es compatible.

| Opción | Argumento nativo |
| --- | --- |
| `agent` | Modo mediante `--mode` (`agent`, `ask` o `plan`) |
| `model` | `--model` opcional |
| `effort` | No compatible; se rechaza |
