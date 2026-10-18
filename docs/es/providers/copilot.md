# GitHub Copilot CLI

Curupira ejecuta [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli)
en modo no interactivo con salida JSON y un id de sesión que él mismo asigna:

```text
copilot --output-format=json --no-ask-user --session-id=<id> [options] --prompt=<prompt>
```

## Instalar e iniciar sesión { #install }

```sh
npm install -g @github/copilot   # o: brew install copilot-cli / winget install GitHub.Copilot
copilot login
```

Consulta la [guía oficial de instalación](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)
para ver los requisitos previos.

En lugar de `copilot login` puedes proporcionar un token. Copilot lee `COPILOT_GITHUB_TOKEN`,
luego `GH_TOKEN` y luego `GITHUB_TOKEN`; los tokens clásicos `ghp_` no se admiten. Si
`GH_TOKEN` ya está exportado para la CLI de GitHub, Copilot lo toma primero, así que
asegúrate de que ese token tenga acceso a Copilot. Curupira nunca lee ni reenvía credenciales.

## Opciones del perfil { #options }

| Opción | Argumento nativo | Notas |
| --- | --- | --- |
| `model` | `--model=<model>` | `auto` deja que Copilot elija. |
| `agent` | `--agent=<agent>` | Un agente personalizado configurado. |
| `effort` | `--reasoning-effort=<level>` | `low`, `medium`, `high`, `xhigh` o `max`. |
| `allow_all_tools = true` | `--allow-all-tools` | Permite todas las herramientas. |
| `allow_tools` | `--allow-tool=<a,b>` | Permite herramientas y patrones seleccionados, como `shell(git:*)` y `write`. |
| `deny_tools` | `--deny-tool=<a,b>` | Prohíbe herramientas; las reglas de denegación tienen prioridad sobre las de permiso. |

Curupira siempre agrega `--no-ask-user`, porque una ejecución desatendida no puede
detenerse a hacer una pregunta, y pasa el prompt como `--prompt=<prompt>` para que un guion
inicial siga siendo texto.

### Permisos de herramientas sin interfaz { #configuration-reference }

Las ejecuciones sin interfaz necesitan permisos de herramientas explícitos. Define
`allow_all_tools = true`, o lista lo permitido en `allow_tools` y lo prohibido en
`deny_tools`. Cada lista se pasa como un único argumento separado por comas, así que una
entrada no puede contener una coma. Curupira nunca agrega flags más amplios como
`--allow-all`, `--yolo` ni omisiones de rutas y URL.

## Ejemplo { #example }

```toml
[agents.profiles.copilot]
provider = "copilot"
model = "auto"
effort = "high"
allow_tools = ["shell(git:*)", "write"]
deny_tools = ["shell(rm:*)"]
```

## Sesiones { #sessions }

Curupira crea un UUID antes de la primera ejecución y lo pasa con `--session-id`. El mismo
flag reanuda una tarea interrumpida; no se usa un flag `--resume` aparte.
