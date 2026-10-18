# pi

Curupira ejecuta [pi](https://www.npmjs.com/package/@earendil-works/pi-coding-agent) en
modo JSON:

```text
pi --mode json [options] -- <prompt>
```

## Instalar e iniciar sesión { #install }

pi necesita Node.js 22.19.0 o posterior.

```sh
npm install -g @earendil-works/pi-coding-agent
```

Inicia sesión con el comando `/login` de pi, o exporta la variable de clave de API de tu
proveedor de modelos. Curupira nunca lee ni guarda credenciales.

## Opciones del perfil { #options }

| Opción | Argumento nativo | Notas |
| --- | --- | --- |
| `model` | `--model <model>` | Un patrón exacto o aproximado; puede incluir `provider/id`. |
| `model_provider` | `--provider <provider>` | Requiere `model`. Se llama así para no chocar con el `provider` de Curupira. |
| `effort` | `--thinking <level>` | `off`, `minimal`, `low`, `medium`, `high`, `xhigh` o `max`. |
| `tools` | `--tools a,b` | Lista de herramientas permitidas que pi puede usar. |
| `exclude_tools` | `--exclude-tools a,b` | Herramientas que se quitan. |
| `approve = true` | `--approve` | Confía en los recursos del proyecto durante esta ejecución. |
| `approve = false` | `--no-approve` | No confía en ellos durante esta ejecución. |
| `agent` | — | No se admite; se rechaza. |

Cuando omites `approve`, se aplica el ajuste de confianza en el proyecto propio de pi. pi no
pregunta antes de cada llamada a una herramienta, y su modo JSON no puede mostrar la
solicitud de confianza; cuando ese ajuste es `ask`, los recursos protegidos del proyecto se
omiten a menos que definas `approve`.

!!! note "Prompts que empiezan con `@`"
    pi interpreta `@path` como la inclusión de un archivo, así que un prompt que empieza con
    `@` puede tratarse como una referencia a un archivo.

## Ejemplo { #example }

```toml
[agents.profiles.pi]
provider = "pi"
model = "anthropic/claude-sonnet-4"
model_provider = "anthropic"
effort = "high"
tools = ["read", "edit", "write"]
exclude_tools = ["bash"]
# approve = true   # confía en los recursos del proyecto durante esta ejecución
```

## Sesiones { #sessions }

pi escribe un encabezado de sesión en su salida JSON; ese id se guarda con la tarea. Una
tarea interrumpida se reanuda con `--session <id>` en el mismo worktree, porque pi agrupa
las sesiones por directorio.
