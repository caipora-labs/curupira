---
template: home.html
title: Curupira
description: Entrega tareas de GitHub, tableros de proyectos y cronogramas cron a la CLI de agente de código que ya usas.
hide:
  - navigation
  - toc
hero:
  eyebrow: Automatizaciones locales para agentes de código
  title: Entrega tu backlog al agente de código que ya usas
  lead: >-
    Curupira vigila fuentes de tareas mediante conectores (GitHub hoy, Monday.com y Azure
    DevOps en desarrollo) y cronogramas cron, y ejecuta cada tarea con Claude Code, Codex,
    Gemini u otra CLI de agente en su propio worktree de Git. Se ejecuta en tu máquina,
    desde un único archivo TOML.
  primary:
    text: Empezar
    href: quick-start/
  secondary:
    text: Cómo funciona
    href: concepts/
  install_label: Instalar
  trace_label: Ejemplo de sesión en la terminal
  trace_caption: >-
    Valida el archivo, previsualiza el prompt exacto y sigue vigilando. Cada tarea
    terminada imprime ok con su identidad y nunca se ejecuta dos veces.
---

<div class="grid cards cp-cols-4" markdown>

-   :material-rocket-launch-outline:{ .lg } **Empezar**

    ---

    Instala la CLI, escribe tu primera automatización y mira el prompt antes de que se ejecute nada.

    [Primeros pasos](quick-start.md) · [Instalación](installation.md)

-   :material-transit-connection-variant:{ .lg } **Orquestador**

    ---

    Configura repositorios, perfiles de agente, automatizaciones, prompts y el ciclo de ejecución.

    [Configuración](configuration.md) · [Ejecutar Curupira](operations.md)

-   :material-puzzle-outline:{ .lg } **Plugins y conectores**

    ---

    Fuentes de tareas para GitHub y más. Cada conector es un plugin que registras por nombre.

    [Resumen de plugins](plugins.md) · [Recetas](recipes.md)

-   :material-code-braces:{ .lg } **Desarrollar extensiones**

    ---

    Escribe tu propio conector en Python o JavaScript con los SDK de Curupira.

    [Resumen de extensiones](extensions.md) · [Protocolo](extensions-protocol.md)

</div>

## Conectores { #connectors }

Un conector es un plugin que le dice a Curupira qué trabajo existe. Elige uno, regístralo en
`settings.toml` y cada tarea que encuentre llega a tu agente.

<div class="grid cards cp-cols-4" markdown>

-   :material-github:{ .lg } **GitHub** <span class="cp-status cp-status--live">Disponible</span>

    ---

    Issues, pull requests y columnas de tableros de Projects, a través de la CLI `gh`.

    [Conector de GitHub](github.md)

-   :material-view-dashboard-outline:{ .lg } **Monday.com** <span class="cp-status cp-status--dev">En desarrollo</span>

    ---

    Elementos de tus tableros de Monday.com como tareas para el agente.

    [Resumen de plugins](plugins.md#catalog)

-   :material-microsoft-azure-devops:{ .lg } **Azure DevOps** <span class="cp-status cp-status--dev">En desarrollo</span>

    ---

    Elementos de trabajo de Azure DevOps como tareas para el agente.

    [Resumen de plugins](plugins.md#catalog)

-   :material-puzzle-plus-outline:{ .lg } **El tuyo** <span class="cp-status cp-status--live">Disponible</span>

    ---

    Cualquier cosa que pueda devolver un elemento a la vez puede ser un conector.

    [Desarrollar extensiones](extensions.md)

</div>

Cron está integrado y no necesita conector: [programa una automatización](automations.md#cron).

## Funciona con la CLI de tu agente { #agents }

Curupira inicia cada agente con su propio comando no interactivo, así que tu sesión, tus
modelos y tus ajustes se quedan donde están.

<div class="cp-agents" markdown>

- [Claude Code](providers/claude.md)
- [Codex](providers/codex.md)
- [Cursor](providers/cursor.md)
- [Gemini CLI](providers/gemini.md)
- [GitHub Copilot CLI](providers/copilot.md)
- [Kilo CLI](providers/kilo.md)
- [OpenCode](providers/opencode.md)
- [pi](providers/pi.md)
- [Qwen Code](providers/qwen.md)

</div>

## Tareas comunes { #tasks }

<div class="cp-tasks" markdown>

- [Instalación](installation.md) <span>Instala Curupira y las CLI de los agentes</span>
- [Cómo funciona](concepts.md) <span>Sigue una tarea desde su fuente hasta el agente</span>
- [Configuración](configuration.md) <span>Entiende cada ajuste del archivo</span>
- [Automatizaciones](automations.md) <span>Elige un trigger y mira un ejemplo mínimo</span>
- [Conector de GitHub](github.md) <span>Filtra issues y pull requests</span>
- [GitHub Projects](github-projects.md) <span>Trabaja desde una columna de un tablero</span>
- [Escribir prompts](prompts.md) <span>Usa condiciones y bucles en un prompt</span>
- [Referencia de campos del prompt](prompt-fields.md) <span>Mira cada campo que puede usar un prompt</span>
- [Recetas](recipes.md) <span>Copia una configuración que funciona</span>
- [Agentes de código](providers.md) <span>Elige o ajusta el agente de código</span>
- [Ejecutar Curupira](operations.md) <span>Úsalo día a día y corrige errores</span>
- [Desarrollar extensiones](extensions.md) <span>Escribe tu propio conector</span>

</div>
