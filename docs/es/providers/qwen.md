# Qwen Code

Curupira ejecuta [Qwen Code](https://github.com/QwenLM/qwen-code) en modo no interactivo
con salida JSON en streaming:

```text
qwen --output-format stream-json [options] --prompt=<prompt>
```

## Instalar e iniciar sesión { #install }

Qwen Code necesita Node.js 22 o posterior.

```sh
npm install -g @qwen-code/qwen-code@latest
qwen   # inicia sesión una vez
```

Qwen Code se encarga de la autenticación. Curupira nunca lee ni guarda credenciales.

## Opciones del perfil { #options }

| Opción | Argumento nativo | Notas |
| --- | --- | --- |
| `model` | `--model <model>` | |
| `approval_mode` | `--approval-mode <mode>` | `plan`, `default`, `auto-edit`, `auto` o `yolo`. |
| `max_session_turns` | `--max-session-turns <n>` | Un entero mayor o igual que `1`. |
| `agent` | — | No se admite; se rechaza. |
| `effort` | — | No se admite; se rechaza. |

!!! warning "`yolo` no es un sandbox"
    `approval_mode = "yolo"` aprueba cada acción automáticamente. La documentación de Qwen
    Code advierte que "does not enable a sandbox" (no habilita un sandbox).

`--max-wall-time` y `--max-tool-calls` no se exponen; `task_timeout_minutes` de Curupira
limita cada ejecución.

## Ejemplo { #example }

```toml
[agents.profiles.qwen]
provider = "qwen"
approval_mode = "auto-edit"
max_session_turns = 40
```

## Sesiones { #sessions }

El id de sesión del stream JSON se guarda con la tarea. Una tarea interrumpida se reanuda
con `--resume <session_id>`.
