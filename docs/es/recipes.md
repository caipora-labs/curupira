---
render_macros: false
---

# Recetas

Copia una, cambia los nombres de los repositorios y ejecuta `curupira validate` seguido de
`curupira run --dry-run`. Todas las recetas asumen la configuración del
[inicio rápido](index.md#quick-start) (un alias de repositorio, un perfil de agente y
el registro de `[plugins.plugins-py]`).

## Resolver issues que tienen un label

```toml
[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
exclude_labels = ["blocked"]
linked_pull_request = false          # omite las issues que ya tienen un pull request
prompt = """
Resuelve la issue #${issue_number}: ${issue_title}

${issue_body}

Abre un pull request cuando termines.
"""
```

## Revisar pull requests que están listos

Solo los pull requests que no son borradores, no tienen conflictos y tienen los checks aprobados.

```toml
[automations.review-pull-requests]
trigger_type = "plugins-py/github-pull-requests"
repository = "api"
repo = "acme/api"
draft = false
mergeable = true
ci_status = "success"
labels = ["review-needed"]
prompt = """
Revisa el pull request #${pull_request_number}: ${pull_request_title}
Rama: ${pull_request_head_ref} -> ${pull_request_base_ref}
Archivos modificados: ${pull_request_changed_files} (+${pull_request_additions} -${pull_request_deletions})

${pull_request_body}
"""
```

## Hacer merge de las actualizaciones de Dependabot

```toml
[automations.merge-dependabot]
trigger_type = "plugins-py/github-pull-requests"
repository = "api"
repo = "acme/api"
author = "app/dependabot"
draft = false
mergeable = true
prompt = """
Analiza el pull request #${pull_request_number} de Dependabot (${pull_request_title}) en ${repo}.
Corrige lo que rompa la actualización, espera los checks y luego haz squash-merge con
`gh pr merge ${pull_request_number} --repo ${repo} --squash`.
"""
```

El perfil del agente necesita `auto_approve = true` para que las escrituras de `gh` sin supervisión no se detengan
a pedir aprobación. Consulta [Proveedores y agentes](providers.md).

## Atender los comentarios de la revisión

Toma los pull requests en los que un revisor pidió cambios. La conversación de la revisión no es un campo
del prompt (consulta [Lo que se deja fuera a propósito](prompt-fields.md#left-out-on-purpose)), así que el prompt le indica al
agente dónde leerla.

```toml
[automations.address-feedback]
trigger_type = "plugins-py/github-pull-requests"
repository = "api"
repo = "acme/api"
review = "changes_requested"
draft = false
prompt = """
El pull request #${pull_request_number} necesita cambios: ${pull_request_title}

Lee la revisión con `gh pr view ${pull_request_number} --repo ${repo} --comments` y
`gh api repos/${repo}/pulls/${pull_request_number}/comments`, y luego haz los cambios solicitados en la
rama ${pull_request_head_ref}.
"""
```

## Trabajar desde una columna del tablero

Una sola automatización atiende tanto las issues como los pull requests que están en la columna `Ready`.

```toml
[automations.board-ready]
trigger_type = "plugins-py/github-project-items"
repository = "api"
owner = "acme"
project = 5
column = "Ready"
repo = "acme/api"
prompt = """
{% if item_type == "pull_request" %}
Revisa el pull request #{{ item_number }} ({{ pull_request_head_ref }} -> {{ pull_request_base_ref }}).
{% else %}
Resuelve la issue #{{ item_number }}: {{ item_title }}
{% endif %}

${item_body}
"""
```

## Adaptar el prompt según los labels

```toml
[automations.triage]
trigger_type = "plugins-py/github-issues"
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
prompt = """
Resuelve la issue #${issue_number}: ${issue_title}

{% if "security" in issue_labels | fromjson %}
Esta issue está relacionada con seguridad. Mantén el cambio mínimo y describe el riesgo en el mensaje del commit.
{% elif "bug" in issue_labels | fromjson %}
Esto es un bug. Escribe primero una prueba que falle y luego corrígelo.
{% else %}
Implementa lo solicitado y agrega pruebas.
{% endif %}

${issue_body}
"""
```

## Usar la prioridad de la tarjeta de un tablero

```toml
[automations.prioritized]
trigger_type = "plugins-py/github-project-items"
repository = "api"
owner = "acme"
project = 5
column = ["Ready"]
prompt = """
{% set card = project_fields | fromjson %}
Prioridad: {{ card.Priority | default("not set") }}

Resuelve #${item_number}: ${item_title}

${item_body}
"""
```

## Una tarea de mantenimiento semanal (sin GitHub)

```toml
[automations.weekly-maintenance]
trigger_type = "cron"
repository = "api"
schedule = "0 9 * * 1"        # todos los lunes a las 09:00 en la zona horaria configurada
prompt = """
Revisa las dependencias y la configuración de CI de ${repository}. Abre un pull request con las
actualizaciones seguras que encuentres. Automatización: ${automation}.
"""
```
