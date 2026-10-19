# OpenCode

Curupira ejecuta [OpenCode](https://opencode.ai) en modo `run` con salida JSON. El directorio
de trabajo del proceso es el worktree de la tarea.

OpenCode 1.x:

```text
opencode run --format json --dir <worktree> [options] -- <prompt>
```

Las ejecuciones headless de OpenCode 2.x usan un servidor privado (`--standalone`) para que la
tarea conserve el directorio del worktree. Las sesiones interactivas de la 2.x no pasan
`--standalone`.

```text
opencode run --standalone --format json [options] -- <prompt>
```

## Instalar e iniciar sesión { #install }

OpenCode 1.x (`opencode-ai`):

```sh
npm install -g opencode-ai
opencode auth login
```

OpenCode 2.x (`@opencode/cli`):

```sh
npm install -g @opencode/cli
opencode auth login
```

OpenCode se encarga de la autenticación de cada proveedor de modelos. Curupira nunca lee ni
guarda credenciales.

Con `api = "auto"` (el predeterminado), Curupira ejecuta `opencode --version` una vez por
binario resuelto y elige el conjunto de flags a partir del primer `x.y.z` que encuentra
(`1.19.3` es 1.x, `opencode v2.0.32` es 2.x). Define `api` cuando esa sonda no puede ver una
versión.

## Opciones del perfil { #options }

| Opción | Argumento nativo | Notas |
| --- | --- | --- |
| `api` | | `"v1"`, `"v2"` o `"auto"` (predeterminado). Selecciona el conjunto de flags de OpenCode 1.x o 2.x. |
| `model` | `--model <provider/model>` | En la 2.x, una variante de razonamiento forma parte del modelo: `provider/model#variant`. |
| `agent` | `--agent <agent>` | Un agente personalizado de OpenCode. |
| `effort` | `--variant` en la 1.x; `#variant` en la 2.x | La 1.x headless pasa `--variant`. La 2.x añade `#<effort>` a `--model`. Se ignora cuando `model` no está definido. Un modelo que ya contiene `#` no se puede combinar con `effort`. |
| `auto_approve = true` | `--auto` | Aprueba los permisos que no se deniegan explícitamente. Úsalo con cuidado. |

| Flag | OpenCode 1.x headless | OpenCode 2.x headless | OpenCode 2.x interactivo |
| --- | --- | --- | --- |
| `--dir <worktree>` | se pasa | se omite; el directorio de trabajo del proceso es el worktree | se omite |
| `--variant` | `effort` | se omite | se omite |
| `--model` | `model` | `model`, o `model#effort` cuando `effort` está definido | igual que la 2.x headless |
| `--standalone` | se omite | siempre se pasa | se omite |
| `--session`, `--agent`, `--format json`, `--auto` | se pasan cuando están configurados | se pasan cuando están configurados | `--agent` y `--auto` cuando están configurados; sin `--format` |

En la 1.x, cada ejecución define `OPENCODE_DB` como `<worktree>.opencode.db`, así que las tareas
en paralelo no comparten sesiones ni entradas de proyecto de OpenCode. En la 2.x, las ejecuciones
conservan tu base de datos de OpenCode: la 2.x guarda allí las credenciales de los proveedores, y
una base nueva informa todos los modelos como no disponibles. El servidor privado `--standalone`
ya mantiene cada tarea en su worktree. `--server` no es una opción de perfil.

## Ejemplo { #example }

```toml
[agents.profiles.opencode]
provider = "opencode"
# api = "auto" # "v1", "v2" o "auto" (predeterminado)
model = "anthropic/claude-sonnet-4"
agent = "build"
# effort = "high" # 1.x: --variant high; 2.x: --model anthropic/claude-sonnet-4#high
```

## Sesiones { #sessions }

El id de sesión es el `sessionID` en la raíz de un evento JSON (1.x y 2.x). Se guarda con la
tarea. Una tarea interrumpida se reanuda con `--session <session_id>`.
