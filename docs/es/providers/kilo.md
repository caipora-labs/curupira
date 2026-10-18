# Kilo CLI

Curupira ejecuta la [CLI de Kilo](https://kilocode.ai/cli) en modo `run` con salida JSON:

```text
kilo run --format json [options] -- <prompt>
```

## Instalar e iniciar sesión { #install }

```sh
npm install -g @kilocode/cli
kilo auth login
```

Kilo y sus integraciones con proveedores se encargan de la autenticación. Curupira nunca
lee ni guarda credenciales.

## Opciones del perfil { #options }

| Opción | Argumento nativo | Notas |
| --- | --- | --- |
| `model` | `--model <provider/model>` | Debe usar la forma `provider/model`; cualquier otra cosa es un error de configuración. |
| `agent` | `--agent <agent>` | Un agente de Kilo existente. |
| `effort` | `--variant <variant>` | Variante de razonamiento específica del proveedor, como `high`, `max` o `minimal`. |
| `auto_approve = true` | `--auto` | Aprueba los permisos que no se deniegan explícitamente. Úsalo con cuidado. |

`--thinking` de Kilo solo muestra los bloques de razonamiento, así que no se usa para
`effort`. Sin `auto_approve`, Kilo rechaza las solicitudes de permiso en las ejecuciones
sin interfaz en lugar de esperar una respuesta.

## Ejemplo { #example }

```toml
[agents.profiles.kilo]
provider = "kilo"
model = "anthropic/claude-sonnet-4"
effort = "high"
```

## Sesiones { #sessions }

Cada registro JSON lleva el id de sesión, que se guarda con la tarea. Una tarea
interrumpida se reanuda con `--session <session_id>`.
