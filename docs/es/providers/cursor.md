# Cursor

Curupira ejecuta la [CLI de Cursor](https://cursor.com/cli) (el comando `agent`) en modo
print con salida JSON en streaming:

```text
agent --print --output-format stream-json [options] -- <prompt>
```

## Instalar e iniciar sesión { #install }

```sh
curl https://cursor.com/install -fsS | bash
agent login
```

La CLI de Cursor se encarga de la autenticación. Curupira nunca lee ni guarda credenciales.

## Opciones del perfil { #options }

| Opción | Argumento nativo | Notas |
| --- | --- | --- |
| `model` | `--model <model>` | `auto` deja que Cursor elija. |
| `agent` | `--mode <mode>` | `agent`, `ask` o `plan`. |
| `force = true` | `--force` | Permite comandos sin confirmación. |
| `trust = true` | `--trust` | Confía en el workspace durante esta ejecución. |
| `effort` | — | No se admite; se rechaza. |

## Ejemplo { #example }

```toml
[agents.profiles.cursor]
provider = "cursor"
model = "auto"
agent = "agent"
force = true
```

## Sesiones { #sessions }

El id de sesión del stream JSON se guarda con la tarea. Una tarea interrumpida se reanuda
con `--resume <session_id>`.
