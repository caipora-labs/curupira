# Desarrollar extensiones

Una extensión es una **fuente de tareas**: un programa pequeño que le dice a Curupira qué
trabajo existe. Los [conectores](plugins.md) (GitHub hoy, Monday.com y Azure DevOps en desarrollo) son
extensiones, y puedes escribir las tuyas para Jira, Linear, una cola en una base de datos o cualquier otra cosa
que pueda producir un elemento a la vez.

Las extensiones se ejecutan como **procesos separados**. Curupira las inicia con `uvx` o
`npx` y se comunica con ellas por stdin y stdout mediante un pequeño
[protocolo JSON-RPC](extensions-protocol.md). Nunca se ejecutan dentro del proceso de
Curupira, y no hay FFI de por medio.

<div class="grid cards" markdown>

-   :material-language-python:{ .lg } **SDK de Python**

    ---

    `curupira-sdk`: decora una función y devuelve un objeto. Solo usa la stdlib; Pydantic es opcional.

    [Escribe una extensión en Python](extensions-python.md)

-   :material-language-javascript:{ .lg } **SDK de JavaScript y TypeScript**

    ---

    `@caipora/curupira-sdk`: `defineTriggers` y un `bin` de npm, iniciado con `npx`.

    [Escribe una extensión en Node.js](extensions-javascript.md)

-   :material-file-document-outline:{ .lg } **Manifiesto y protocolo**

    ---

    Framing, métodos, resultados, códigos de error y el manifiesto `curupira-extension.toml`.

    [Lee la referencia](extensions-protocol.md)

</div>

## Qué hace una extensión { #responsibilities }

| Una extensión... | Curupira (el host)... |
| --- | --- |
| Declara sus triggers y los ajustes que acepta cada uno | Lee el TOML y pasa los ajustes de cada automatización |
| Valida esos ajustes | Informa los errores de validación desde `curupira validate` |
| Devuelve el **siguiente elemento** como una lista plana de pares clave/valor, o nada | Deduplica, planifica y limita la concurrencia |
| Recibe avisos cuando una tarea empieza y cuando termina | Clona, crea worktrees, ejecuta `setup_script` |
| Escribe los logs en stderr | Renderiza el prompt e inicia el agente de código |

Las extensiones no deben elegir un agente de código, construir líneas de comando de
agentes, clonar repositorios ni gestionar worktrees. Los agentes de código están integrados
en el host; dar soporte a un agente nuevo es un cambio en el propio Curupira.

## Registrar una extensión { #register }

Cada extensión se registra en `settings.toml` con un alias que eliges, junto con el
lanzador y sus argumentos. Luego las automatizaciones se refieren a un trigger como
`<alias>/<trigger>`.

=== "Python (uvx)"

    ```toml
    [plugins.acme]
    type = "uvx"
    args = ["--from", "acme-curupira==1.2.0", "acme-curupira"]
    tools = ["*"]

    [automations.triage]
    trigger_type = "acme/tickets"
    repository = "api"
    prompt = "Triage ${title}"
    ```

=== "Node.js (npx)"

    ```toml
    [plugins.acme]
    type = "npx"
    args = ["--yes", "@acme/curupira-ext@1.2.0"]
    tools = ["*"]

    [automations.triage]
    trigger_type = "acme/tickets"
    repository = "api"
    prompt = "Triage ${title}"
    ```

`args` se pasan como argumentos separados, nunca a través de un shell. Fija una versión
para que todas las máquinas ejecuten el mismo código. `tools` conserva solo los triggers
que coinciden (`github-*`) o los descarta (`!github-project-*`).

## Inspeccionar plugins { #manage }

`curupira plugins` lista los triggers que puedes usar y los ajustes que acepta cada uno:

```sh
curupira plugins list
curupira plugins info curupira-plugins
```

`plugins list` también muestra el cron integrado y los proveedores de agentes de código
integrados (etiquetados como `agent:<name>` con origen `built-in`). Listar lee los
manifiestos `curupira-extension.toml` y **nunca ejecuta código de las extensiones**.

### Requisitos de ejecución { #runtime-requirements }

| Origen | Necesita en el `PATH` |
| --- | --- |
| Plugins `type = "uvx"` | `uvx` (de [uv](https://docs.astral.sh/uv/)) |
| Plugins `type = "npx"` | `npx` (Node.js 20+) |
| Cron y agentes de código integrados | las CLI de agentes que configures, más `git` |

Si falta un lanzador, `curupira validate` dice cuál.

## Seguridad { #security }

Las extensiones de terceros se ejecutan con los privilegios de tu usuario. Un subproceso no
es un sandbox. Instala solo paquetes en los que confíes y fija sus versiones. Curupira nunca
instala paquetes al listar plugins.

El texto que devuelve una extensión suele venir de personas fuera de tu equipo (títulos de
issues, comentarios). Termina en un prompt; lee
[el texto de las tareas no es confiable](github.md#security) antes de automatizar fuentes públicas.
