# Plugins y conectores

Un **plugin** es un programa que le dice a Curupira qué trabajo existe. Un **conector** es un
plugin para una herramienta en la que ya trabajas, como GitHub. Curupira inicia el plugin, le
pide el siguiente elemento y se lo entrega a tu agente de código en su propio worktree de Git.

Los conectores no están atados a un único servicio. GitHub es el primero en salir, Monday.com y
Azure DevOps están en desarrollo, y puedes [escribir los tuyos](extensions.md).

## Conectores { #catalog }

<div class="grid cards" markdown>

-   :material-github:{ .lg } **GitHub** <span class="cp-status cp-status--live">Disponible</span>

    ---

    Issues, pull requests y columnas de tableros de Projects, a través de la CLI `gh`. Ningún
    token va en tu configuración.

    [Issues y pull requests de GitHub](github.md) · [Projects](github-projects.md)

-   :material-view-dashboard-outline:{ .lg } **Monday.com** <span class="cp-status cp-status--dev">En desarrollo</span>

    ---

    Elementos de tus tableros de Monday.com como tareas para el agente.

    Todavía no se ha publicado.

-   :material-microsoft-azure-devops:{ .lg } **Azure DevOps** <span class="cp-status cp-status--dev">En desarrollo</span>

    ---

    Elementos de trabajo de Azure DevOps como tareas para el agente.

    Todavía no se ha publicado.

-   :material-puzzle-plus-outline:{ .lg } **El tuyo** <span class="cp-status cp-status--live">Disponible</span>

    ---

    Un conector para Jira, Linear, una cola en una base de datos o cualquier cosa que pueda
    devolver un elemento a la vez.

    [Desarrollar extensiones](extensions.md)

</div>

Todos los conectores funcionan igual para ti: lo registras una vez y luego apuntas las
automatizaciones a sus triggers. Solo cambian los nombres de los triggers y sus filtros.

Los triggers que existen hoy:

| Trigger | Fuente | Necesita |
| --- | --- | --- |
| [`plugins-py/github-issues`](github.md#minimal-issue-automation) | Issues de GitHub | `gh auth login` |
| [`plugins-py/github-pull-requests`](github.md) | Pull requests de GitHub | `gh auth login` |
| [`plugins-py/github-project-items`](github-projects.md) | Columnas de tableros de GitHub Projects | `gh` con el alcance `read:project` |
| [`cron`](automations.md#cron) | Una agenda local, integrada en Curupira | Nada |

## Registrar un conector { #register }

Un plugin se registra con un alias que eliges, junto con el lanzador que lo inicia. Las
automatizaciones direccionan luego un trigger como `<alias>/<trigger>`.

```toml
[plugins.plugins-py]                                  # (1)!
type = "uvx"
args = ["--from", "curupira-plugins", "curupira-plugins"]

[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"             # (2)!
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
prompt = "Resolve issue #${issue_number}: ${issue_title}"
```

1.  El alias lo eliges tú. `plugins-py` es la convención usada en toda esta documentación para
    el conector oficial de GitHub.
2.  `<alias>/<trigger>`: el trigger proviene del plugin registrado arriba. Las demás claves
    son los filtros de ese trigger.

El paquete se ejecuta con `uvx`, así que necesitas [uv](https://docs.astral.sh/uv/) en el
`PATH`. Los plugins escritos para Node.js se ejecutan con `npx`; consulta
[Registrar una extensión](extensions.md#register).

=== "Fijar una versión"

    ```toml
    [plugins.plugins-py]
    type = "uvx"
    args = ["--from", "curupira-plugins==0.3.0", "curupira-plugins"]
    ```

    Así todas las máquinas ejecutan la misma versión del plugin.

=== "Conservar algunos triggers"

    ```toml
    [plugins.plugins-py]
    type = "uvx"
    args = ["--from", "curupira-plugins", "curupira-plugins"]
    tools = ["github-*", "!github-project-*"]
    ```

    `tools` conserva los triggers que coinciden; un patrón con `!` los descarta.

## Usar el conector de GitHub { #github }

Inicia sesión una vez. El conector llama a `gh` con tu cuenta, así que ve exactamente los
repositorios y tableros que tú ves.

```sh
gh auth login
gh auth refresh -s read:project   # solo para columnas de tableros de Projects
```

Consulta [Alcances del token](github.md#prerequisites) para ver los detalles y luego elige un
trigger:

<div class="grid cards" markdown>

-   :material-alert-circle-outline:{ .lg } **Issues**

    ---

    Labels, asignados, hitos, pull requests vinculados y búsqueda libre.

    [`github-issues`](github.md#minimal-issue-automation)

-   :material-source-pull:{ .lg } **Pull requests**

    ---

    Borradores, estado de revisión, estado de CI, autores como Dependabot y mergeabilidad.

    [`github-pull-requests`](github.md)

-   :material-view-column-outline:{ .lg } **Columnas de tableros de Projects**

    ---

    Tarjetas de una columna de un GitHub Project, con sus campos personalizados.

    [`github-project-items`](github-projects.md)

-   :material-book-open-variant:{ .lg } **Recetas**

    ---

    Configuraciones completas para copiar: revisiones, Dependabot, feedback y tableros.

    [Recetas](recipes.md)

</div>
