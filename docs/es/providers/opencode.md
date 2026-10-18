# OpenCode

Curupira ejecuta [OpenCode](https://opencode.ai) en modo `run` con salida JSON, apuntando
al worktree de la tarea:

```text
opencode run --format json --dir <worktree> [options] -- <prompt>
```

## Instalar e iniciar sesión { #install }

```sh
npm install -g opencode-ai
opencode auth login
```

OpenCode se encarga de la autenticación de cada proveedor de modelos. Curupira nunca lee ni
guarda credenciales.

## Opciones del perfil { #options }

| Opción | Argumento nativo | Notas |
| --- | --- | --- |
| `model` | `--model <provider/model>` | |
| `agent` | `--agent <agent>` | Un agente personalizado de OpenCode. |
| `effort` | `--variant <variant>` | Variante de razonamiento específica del proveedor. |
| `auto_approve = true` | `--auto` | Aprueba los permisos que no se deniegan explícitamente. Úsalo con cuidado. |

Cada ejecución define `OPENCODE_DB` con una base de datos junto al worktree, así que las
tareas en paralelo no comparten el estado de OpenCode.

## Ejemplo { #example }

```toml
[agents.profiles.opencode]
provider = "opencode"
model = "anthropic/claude-sonnet-4"
agent = "build"
```

## Sesiones { #sessions }

El id de sesión de los eventos JSON se guarda con la tarea. Una tarea interrumpida se
reanuda con `--session <session_id>`.
