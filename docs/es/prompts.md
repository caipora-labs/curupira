---
render_macros: false
---

# Cómo escribir prompts

El `prompt` de una automatización es el texto que recibe tu agente de código. Lo escribes en
`settings.toml`; Curupira completa los detalles de cada tarea antes de que el agente arranque.

Empieza simple y agrega lógica solo cuando la necesites.

## 1. Inserta campos con `${name}`

```toml
prompt = "Resuelve la issue ${issue_number}: ${issue_title}\n\n${issue_body}"
```

Usa una cadena multilínea para prompts más largos. En TOML, las cadenas `"""` procesan escapes como
`\n`; las cadenas `'''` se toman literalmente:

```toml
prompt = """
Resuelve la issue ${issue_number} en ${repo}.

${issue_body}
"""
```

Las listas (como los labels) se insertan como JSON, por ejemplo `["bug","security"]`.

## 2. Hazlo dinámico

Para cualquier cosa más allá de insertar valores, usa la sintaxis de Jinja. Puedes mezclarla libremente con `${name}`.

| Quieres | Escribe |
| --- | --- |
| Un valor | `{{ issue_title }}` |
| Un valor de respaldo para un valor vacío u opcional | `{{ issue_milestone \| default("none") }}` |
| Texto solo en algunos casos | `{% if "security" in issue_labels %}...{% endif %}` |
| Dos alternativas | `{% if item_type == "pull_request" %}...{% else %}...{% endif %}` |
| Repetir para cada elemento de una lista | `{% for label in issue_labels %}- {{ label }}\n{% endfor %}` |
| Acortar un texto largo | `{{ issue_body \| truncate(2000) }}` |
| Recorrer los últimos comentarios | `{% for c in issue_comments \| fromjson %}{{ c.author }}: {{ c.body }}{% endfor %}` |

Ejemplo: una automatización que se adapta a lo que recibe (más en [Recetas](recipes.md)):

```toml
[automations.work-ready-column]
trigger_type = "plugins-py/github-project-items"
repository = "api"
owner = "acme"
project = 5
column = ["Ready"]
prompt = """
{% if item_type == "pull_request" %}
Revisa el pull request #{{ item_number }} ({{ pull_request_head_ref }} -> {{ pull_request_base_ref }}).
El CI está en {{ pull_request_ci_status | default("unknown") }}.
{% else %}
Resuelve la issue #{{ item_number }}: {{ item_title }}
{% endif %}

{% if "security" in item_labels %}
Esta es una issue de seguridad. Mantén el cambio mínimo y explica el riesgo en el mensaje del commit.
{% endif %}

${item_body}
"""
```

Notas:

- El salto de línea después de una etiqueta `{% ... %}` se conserva, así que un bloque en su propia línea deja una
  línea en blanco. Usa `{%- ... -%}` para recortar el espacio en blanco alrededor de una etiqueta cuando importe.
- Jinja tiene muchos más [filtros y pruebas integrados](https://docs.rs/minijinja/latest/minijinja/filters/index.html)
  (`upper`, `join`, `length`, `first`, `selectattr`, ...).

## Campos

Toda automatización recibe estos:

`${repo}` (el `owner/name` de GitHub), `${repository}` (el alias del checkout), `${automation_id}`
(también `${automation}`), `${task_type}`, `${task_number}`, `${task_title}`, `${task_body}`,
`${task_url}`. En las tareas de cron, `${task_number}` es la hora programada.

Cada trigger agrega sus propios campos. La lista completa está en la [referencia de campos del prompt](prompt-fields.md),
y [Recetas](recipes.md) incluye automatizaciones completas para copiar.

## Cómo revisar tu prompt

1. `curupira --config settings.toml validate` comprueba la sintaxis y que cada campo que uses
   exista. Un error de tipeo recibe una sugerencia:

   ```text
   automation "work-ready-column": prompt uses unknown field(s) "item_titel"
   (did you mean "item_title"?). Available fields: ...
   ```

2. `curupira --config settings.toml run --dry-run` encuentra una tarea que coincida e imprime el prompt
   final, sin clonar ni iniciar un agente. Es la forma más rápida de ver qué recibirá el
   agente.

Un campo que existe pero no tiene valor para una tarea dada (por ejemplo, un campo de pull request en
una issue) es un error cuando se ejecuta la tarea, no una cadena vacía. Protégelo con `default("")` o
con un `{% if %}`.

## Seguridad

Los títulos, los cuerpos y los comentarios vienen de otras personas. Su texto se inserta como texto plano
y nunca se interpreta como plantilla, así que `{{ ... }}` dentro del cuerpo de una issue no hace nada. Aun así,
puede intentar manipular al agente, por lo que debes seguir los consejos de
[las notas de seguridad](github.md#security).
