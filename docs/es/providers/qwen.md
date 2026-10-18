# Qwen Code

Instala Qwen Code con Node.js 22 o posterior:

```bash
npm install -g @qwen-code/qwen-code@latest
```

Curupira ejecuta `qwen --output-format stream-json --prompt=<message>`. Reanuda una sesión
conocida con `--resume <session_id>`. Qwen Code se encarga de la autenticación; Curupira no
gestiona las credenciales del proveedor.

| Opción del perfil | Argumento nativo |
| --- | --- |
| `model` | `--model` opcional |
| `approval_mode` | `--approval-mode` opcional (`plan`, `default`, `auto-edit`, `auto` o `yolo`) |
| `max_session_turns` | `--max-session-turns` opcional (entero ≥ 1) |
| `agent` | No compatible; se rechaza |
| `effort` | No compatible; se rechaza |

`approval_mode = "yolo"` habilita la aprobación automática. La documentación de Qwen Code advierte
que el modo YOLO “no habilita un sandbox”.

Las opciones `--max-wall-time` y `--max-tool-calls` no se exponen; el timeout de tareas de Curupira
acota cada ejecución.

::: curupira.agents.qwen.QwenCodeCliProfile
