---
render_macros: false
---

# GitHub Projects (columnas del tablero)

`plugins-py/github-project-items` convierte una columna de un tablero de GitHub Projects en una cola de trabajo.
Mueve una tarjeta a la columna que elegiste y Curupira entrega esa issue o ese pull request a tu
agente de código. Funciona con proyectos de usuario y de organización (los nuevos "Projects", también llamados
Projects v2).

```toml
[automations.work-ready-column]
trigger_type = "plugins-py/github-project-items"
repository = "api"          # alias del checkout donde se ejecuta el agente
owner = "acme"              # usuario u organización dueña del proyecto
project = 5                 # el número que aparece en la URL del proyecto
column = "Ready"            # un valor del campo Status
prompt = """
{% if item_type == "pull_request" %}Revisa{% else %}Resuelve{% endif %} #${item_number}: ${item_title}

${item_body}
"""
```

## Antes de empezar

1. Inicia sesión con la CLI de GitHub y agrega el alcance de proyectos. Sin `read:project`, GitHub
   informa que el proyecto no existe.

   ```sh
   gh auth login
   gh auth refresh -s read:project
   ```

2. Busca el **número del proyecto**. Es el número al final de la URL del proyecto:
   `https://github.com/orgs/acme/projects/5` es el proyecto `5` del propietario `acme`. También puedes listarlos:

   ```sh
   gh project list --owner acme        # la primera columna es el número
   gh project list --owner @me         # tus proyectos personales
   ```

3. Busca los **nombres exactos de las columnas**. Son las opciones del campo `Status`:

   ```sh
   gh project field-list 5 --owner acme
   ```

## Campos

| Campo | Valor por defecto | Significado |
| --- | --- | --- |
| `owner` | *(obligatorio)* | Login del usuario u organización dueña del proyecto |
| `project` | *(obligatorio)* | Número del proyecto |
| `column` | *(obligatorio)* | Un nombre de columna o una lista. No distingue mayúsculas de minúsculas |
| `status_field` | `"Status"` | El campo de selección única que contiene la columna. Cámbialo si tu tablero usa otro campo, por ejemplo `"Stage"` |
| `content` | `"all"` | `"issue"`, `"pull_request"` o `"all"` |
| `repo` | ninguno | Solo elementos de este `owner/name`. Los proyectos suelen abarcar muchos repositorios |
| `state` | `"open"` | `"open"`, `"closed"` o `"all"` |
| `labels` | ninguno | Todos los labels indicados deben estar en el elemento |
| `exclude_labels` | ninguno | Ninguno de los labels indicados puede estar en el elemento |
| `assignee` | ninguno | Un login, `"none"` (sin asignar) o `"any"` (asignado a alguien) |
| `author` | ninguno | El login del autor |

Las tarjetas borrador (notas que todavía no son issues) y las tarjetas archivadas siempre se omiten, porque
no tienen un repositorio donde trabajar.

!!! note "Elementos cerrados"
    `state` es `"open"` por defecto, así que una issue cerrada que sigue en una columna se
    ignora. Usa `state = "all"` si quieres que la columna sea la única regla.

## ¿En qué repositorio trabaja el agente?

Un tablero puede contener elementos de varios repositorios, pero cada automatización se ejecuta en un único checkout,
el alias `repository`. Dos configuraciones comunes:

- **Un repositorio por tablero.** Define `repo = "acme/api"` y `repository = "api"`.
- **Varios repositorios.** Crea una automatización por repositorio, cada una con su propio `repo`
  y `repository`, todas apuntando al mismo proyecto y columna.

En el prompt, `${repo}` es siempre el repositorio del elemento encontrado, lo cual es útil para
los comandos `gh`.

## Un flujo de trabajo guiado por columnas

Usa una columna por etapa y una automatización por etapa. Los agentes pasan de una a la siguiente cuando
tú (o una automatización posterior) mueves la tarjeta:

| Columna | Automatización | Qué hace el agente |
| --- | --- | --- |
| `Ready` | `column = "Ready"` | Implementa la issue y abre un pull request |
| `Review` | `column = "Review"`, `content = "pull_request"` | Revisa el pull request y comenta |

Cada elemento se procesa una sola vez: cuando el agente termina con éxito, esa issue o ese pull request
se recuerda y la misma automatización no lo vuelve a ejecutar, incluso si arrastras la tarjeta de vuelta a
la columna. Consulta [Deduplicación](github.md#deduplication). Las tarjetas cuya ejecución del agente falló se
intentan de nuevo después de un reinicio.

## Qué puede usar el prompt

Los elementos del proyecto exponen los campos `${item_*}`, `${project_*}` y algunos `${pull_request_*}`. Consulta
la [referencia de campos del prompt](prompt-fields.md#project-items). La
columna donde se encontró el elemento es `${project_column}`, y cada campo de la tarjeta (por ejemplo
`Priority` o `Iteration`) está en `${project_fields}` como JSON:

```toml
prompt = """
{% set fields = project_fields | fromjson %}
Prioridad: {{ fields.Priority | default("none") }}
"""
```

## Solución de problemas

| Mensaje o síntoma | Causa y solución |
| --- | --- |
| `GitHub project 5 not found for 'acme'` | El propietario o el número son incorrectos, o el token no tiene `read:project`. Ejecuta `gh auth refresh -s read:project` y revisa la URL |
| No se encuentra nada, pero la columna tiene tarjetas | Las tarjetas están cerradas (`state = "all"`), son borradores, pertenecen a otro `repo`, o el nombre de la columna es distinto. Compara con `gh project field-list` |
| Un `status_field` personalizado no encuentra nada | Usa el nombre exacto del campo, por ejemplo `status_field = "Stage"` |
| `column: Value error` de `validate` | `column` está vacío. Indica al menos un nombre |
