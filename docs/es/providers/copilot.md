# GitHub Copilot CLI

Curupira ejecuta `copilot` de forma no interactiva con salida JSONL, un ID de sesión persistido y
`--no-ask-user`. La CLI termina cuando se completa el prompt. Por ahora Curupira devuelve el
JSONL capturado sin cambios porque el esquema de eventos de las ejecuciones programáticas con prompt no está
documentado; todavía no extrae un mensaje final del asistente.

## Instalación

Instala `@github/copilot` con npm (`npm install -g @github/copilot`), usa
`brew install copilot-cli` en Homebrew, o usa `winget install GitHub.Copilot` en Windows.

Consulta la [guía oficial de instalación](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)
para ver los requisitos previos y los detalles específicos de cada plataforma.

## Autenticación

Autentícate con `copilot login`, o proporciona un token compatible en el entorno. La precedencia
de los tokens es `COPILOT_GITHUB_TOKEN`, luego `GH_TOKEN` y después `GITHUB_TOKEN`. Los personal access tokens
clásicos `ghp_` no son compatibles con Copilot CLI.

Si `GH_TOKEN` ya está exportado para la CLI de GitHub, Copilot lo toma antes que
`GITHUB_TOKEN`; asegúrate de que ese token tenga acceso a Copilot. Curupira no gestiona ni reenvía
credenciales de autenticación.

## Opciones del perfil

| Opción del perfil | Argumento nativo |
| --- | --- |
| Mensaje de la tarea | `--prompt=<message>`; la forma con signo igual conserva un guion inicial en el prompt |
| Sesión | `--session-id=<id>` tanto para ejecuciones nuevas como reanudadas; Curupira asigna el nuevo UUID |
| Salida | `--output-format=json`; Curupira conserva el JSONL capturado sin cambios |
| Preguntas al usuario | `--no-ask-user`, siempre habilitado por Curupira |
| `model` | `--model=<model>` (Copilot CLI acepta `auto`) |
| `agent` | `--agent=<agent>` para un agente personalizado configurado |
| `effort` | `--reasoning-effort=<level>`: `low`, `medium`, `high`, `xhigh` o `max` |
| `allow_all_tools` | `--allow-all-tools` |
| `allow_tools` | Un argumento `--allow-tool=<comma-separated-patterns>` |
| `deny_tools` | Un argumento `--deny-tool=<comma-separated-patterns>`; las reglas de denegación prevalecen sobre las de permiso |

Curupira siempre pasa `--no-ask-user`: Copilot no puede detenerse a hacer una pregunta mientras una tarea
se ejecuta sin supervisión. Cada ejecución también pasa `--output-format=json` y
`--session-id=<id>`. Las ejecuciones nuevas usan el UUID que Curupira persistió antes de lanzar la CLI;
las ejecuciones reanudadas pasan su ID de sesión persistido con el mismo flag. No se usa
ningún flag `--resume` aparte. El prompt de la tarea se pasa como `--prompt=<message>` para que un guion inicial siga
formando parte del prompt.

### Permisos de herramientas sin interfaz

El uso de herramientas sin interfaz necesita autorización explícita. Define `allow_all_tools = true` para permitir
todas las herramientas compatibles con Copilot CLI, o define `allow_tools` para permitir explícitamente herramientas
y patrones concretos como `shell(git:*)` y `write`. `deny_tools` puede denegar explícitamente
herramientas; las denegaciones tienen prioridad sobre los permisos. Las entradas de herramientas no pueden contener comas porque
Curupira pasa cada lista como un único argumento de CLI separado por comas.

Curupira nunca añade flags más amplios como `--allow-all`, `--yolo` ni omisiones de rutas o URL.

## Referencia de configuración { #configuration-reference }

::: curupira.agents.copilot.CopilotCliProfile
    options:
      inherited_members:
        - model
      members:
        - model

### Campo `model` heredado

El perfil común de CLI aporta `model`; Copilot lo traduce a `--model=<model>`.
