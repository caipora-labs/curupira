# Referencia de automatizaciones

`curu` es el alias corto de `curupira`; ambos ejecutan los mismos comandos. Esta página es
el mapa para quien empieza con las automatizaciones de Curupira: qué triggers existen, un
ejemplo mínimo de TOML para cada uno, qué placeholders de prompt están disponibles y los
primeros comandos que debes ejecutar. El detalle campo por campo está en las guías
dedicadas y en [Configuración](configuration.md); esta página lo resume y enlaza.

Una **automatización** es una tabla `[automations.<name>]`. Observa una sola fuente
(`trigger_type`), apunta a un repositorio Git `[repositories.<alias>]` y lleva una
plantilla de `prompt` para una CLI de agente de código. Todas las automatizaciones
comparten un mismo flujo de descubrimiento, programación y ejecución.

## Resumen de triggers { #trigger-overview }

{{ triggers_table("es") }}

Los conectores registrados en `[plugins.<alias>]` añaden más tipos de trigger, consulta
[Plugins y conectores](plugins.md). `curu plugins list` muestra cada tipo disponible y sus
campos de prompt.

## Seguridad: el texto de las tareas no es confiable { #security-task-text-is-untrusted }

Los títulos y cuerpos de los issues y pull requests de GitHub son entrada no confiable.
Curupira los coloca en el prompt del agente de código (`${issue_title}`, `${issue_body}`,
`${pull_request_title}`, `${pull_request_body}`, `${item_body}`). Un autor hostil puede intentar dirigir al agente. Restringe lo que llega
al agente con `labels`, `author` o `assignee`. Revisa qué puede ejecutar el perfil del
agente en el repositorio. Ejecuta automatizaciones solo en repositorios donde confíes en
todas las personas que pueden escribir texto.

## Primeros pasos { #first-use-path }

1. [Instala Curupira](installation.md) y solo las CLI externas que necesiten tus
   automatizaciones (por ejemplo `gh`) más la CLI del agente de código de tu perfil:

   ```bash
   npm install -g @caipora/curupira
   # o: uv tool install curupira
   ```

2. Copia un archivo de configuración mínimo (o parte de `curupira.example.toml`) y valida
   sin llamar a CLI externas ni escribir estado:

   ```bash
   curupira --config path/to/settings.toml validate
   ```

3. Previsualiza una tarea coincidente sin clonar un repositorio ni iniciar un agente:

   ```bash
   curupira --config path/to/settings.toml run --dry-run
   ```

4. Ejecuta una vez todas las tareas disponibles en ese momento (añade `--size N` para
   limitar) o sigue consultando con `--watch`:

   ```bash
   curupira --config path/to/settings.toml run
   curupira --config path/to/settings.toml run --size 1
   curupira --config path/to/settings.toml run --watch
   ```

`--dry-run` no se puede combinar con `--watch` ni con `--size`. `--size` solo se aplica
cuando ejecutas las tareas una vez (no con `--watch`). Los detalles operativos y los
códigos de salida están en [Operaciones](operations.md).

Cada ejemplo siguiente repite `[agents.defaults]` y `[agents.profiles.opencode]` para que
valide por sí solo. En el ejemplo de cron, `timezone = "UTC"` es la zona horaria usada
para evaluar la programación.

## Issues de GitHub { #github-issues }

Encuentra issues usando los filtros que defines en TOML. Requiere la
[CLI de GitHub](https://cli.github.com/) (`gh auth login`). Guía completa:
[Fuentes de tareas de GitHub](github.md).

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "opencode"

[agents.profiles.opencode]
provider = "opencode"

[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
linked_pull_request = false
prompt = "Resolve issue ${issue_number}: ${issue_title}\n\n${issue_body}"
```

**Placeholders:** `${repository}` y `${automation}` del host, más las claves que
devuelve este trigger, entre ellas `${repo}`, `${issue_number}`, `${issue_title}`,
`${issue_body}` y `${issue_url}`.

**Qué recibe el agente:** la cadena `prompt` ya renderizada, con el agente trabajando en
el repositorio Git indicado por `repository`. `${repo}` es una clave que devuelve el
trigger de GitHub; `${repository}` es la identidad del forge derivada del remote de Git.

## Pull requests de GitHub { #github-pull-requests }

Encuentra pull requests usando los filtros que defines en TOML (incluidas comprobaciones
opcionales de merge después del listado). Requiere `gh`. Guía completa:
[Fuentes de tareas de GitHub](github.md).

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "opencode"

[agents.profiles.opencode]
provider = "opencode"

[automations.review-pull-requests]
trigger_type = "plugins-py/github-pull-requests"
repository = "api"
repo = "acme/api"
labels = ["review-needed"]
draft = false
prompt = """
Review pull request ${pull_request_number}: ${pull_request_title}

${pull_request_body}

Branch: ${pull_request_head_ref} -> ${pull_request_base_ref}
"""
```

**Placeholders:** `${repository}` y `${automation}` del host, más las claves que
devuelve este trigger, entre ellas `${pull_request_number}`,
`${pull_request_title}`, `${pull_request_body}`, `${pull_request_url}`,
`${pull_request_is_draft}`, `${pull_request_head_ref}` y
`${pull_request_base_ref}`.

**Qué recibe el agente:** el prompt de revisión ya renderizado, en el repositorio Git
indicado por `repository`. Los booleanos se renderizan como `true` / `false`. Un campo cuyo valor es `None`
se renderiza como `null`. Un `${key}` que el resultado no contiene se deja sin cambios.

## Cron { #cron }

Se ejecuta según una programación local que defines con un `schedule` de cinco campos. No
se necesita ninguna CLI externa de tablero ni de seguimiento de issues. Las opciones de
programación (zona horaria, fechas de inicio y fin) están en
[Configuración](configuration.md#scheduling-and-state).

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "opencode"
timezone = "UTC"

[agents.profiles.opencode]
provider = "opencode"

[automations.weekly-maintenance]
trigger_type = "cron"
repository = "api"
schedule = "0 9 * * 1"
prompt = "Perform weekly maintenance for ${repository} (${automation})."
```

**Placeholders:** solo `${repository}` y `${automation}`. Cron no devuelve
pares del trigger. El campo opcional `timezone` reemplaza a
`[agents.defaults].timezone`; los campos opcionales `start_date` / `end_date` delimitan
la ventana inclusiva.

**Qué recibe el agente:** el prompt de mantenimiento ya renderizado, en el repositorio
Git indicado por `repository`, cuando la programación toca. Las ejecuciones atrasadas se
fusionan en una sola ejecución pendiente, y la misma automatización nunca se ejecuta dos
veces al mismo tiempo.

## Errores de configuración comunes { #common-configuration-errors }

| Síntoma | Causa probable | Solución |
| --- | --- | --- |
| `unknown trigger type: …` | Error tipográfico, o el plugin no está registrado | Compara `trigger_type` con `curu plugins list` |
| Errores de alias de repositorio / falta el repositorio | `repository` no coincide con una clave `[repositories.<alias>]` | Alinea el alias y comprueba que `remote` sea una URL de Git completa |
| Placeholder sin reemplazar en el prompt | `${name}` no es una variable del host y el trigger no devolvió esa clave | Usa una clave que devuelva el trigger; consulta la [Referencia de campos de prompt](prompt-fields.md). `validate` sugiere la clave más cercana |
| `prompt uses unknown field(s)` de `validate` | Un `{{ name }}` (o un `${name}` que parece un error tipográfico) no es una clave de este trigger | Corrige el nombre; el mensaje lista los campos disponibles |
| Error de plantilla del prompt con un número de línea | Sintaxis Jinja inválida, por ejemplo un bloque `if` sin su `endif` | Corrige la línea indicada. Para imprimir llaves dobles literales, usa un bloque `raw`, consulta [Cómo escribir prompts](prompts.md#values-are-text) |
| `Required executable not found: gh` | La CLI no está en el `PATH` | Instala y autentica la CLI de ese trigger |
| `schedule must be a valid five-field cron expression` | Cron de seis campos o expresión inválida | Usa cinco campos (`minute hour day-of-month month day-of-week`) |
| `repo must use the owner/repository format` | El `repo` de GitHub no es `owner/name` | Usa `acme/api`, no una URL |
| No hay tareas programadas | Los filtros no coinciden con nada | Amplía o quita los filtros de labels / ramas; los ciclos vacíos no son un error |
| `validate` termina con `2` | Estructura del TOML, claves de configuración desconocidas o errores del prompt | Lee el mensaje de validación; los modelos rechazan las claves desconocidas |

`curu validate` comprueba la estructura del TOML, la configuración del trigger y el prompt (sintaxis y nombres de campos)
sin llamar a APIs externas. `curu run` y `curu run --watch` necesitan que las CLI de tus triggers y
la CLI del agente elegido estén instaladas y autenticadas.
