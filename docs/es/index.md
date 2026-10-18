# Curupira

Curupira ejecuta automatizaciones en tu máquina. Vigila una fuente de trabajo (issues de GitHub, pull
requests, una columna de un tablero de GitHub Projects o un cronograma cron) y entrega cada elemento a
una CLI de agente de código que ya uses, como Claude Code, Codex, Gemini u OpenCode. Cada
tarea se ejecuta en su propio worktree de Git, así que tu propio checkout nunca se toca.

Todo se configura en un único archivo TOML, `~/.curupira/settings.toml`.

## Inicio rápido (unos 5 minutos) { #quick-start }

Necesitas [Git](https://git-scm.com/), la [CLI de GitHub](https://cli.github.com/) (`gh`) y una
CLI de agente de código. Los detalles están en [Instalación](installation.md).

**1. Instala e inicia sesión**

```sh
uv tool install 'curupira[github]'
gh auth login
```

**2. Crea `~/.curupira/settings.toml`**

Esto resuelve los issues que tengan el label `agent-ready`:

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"   # donde trabaja el agente

[agents.defaults]
profile = "claude"
timezone = "UTC"

[agents.profiles.claude]
provider = "claude"

[plugins.plugins-py]                          # los triggers oficiales de GitHub
type = "uvx"
args = ["--from", "curupira-plugins", "curupira-plugins"]

[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"
repository = "api"
repo = "acme/api"                             # el repositorio de GitHub a vigilar
labels = ["agent-ready"]
prompt = """
Resolve issue #${issue_number}: ${issue_title}

${issue_body}
"""
```

**3. Valídalo, previsualízalo y ejecútalo**

```sh
curupira validate      # ¿el archivo es correcto?
curupira run --dry-run # qué tarea se ejecutaría y el prompt exacto que recibe el agente
curupira run --watch   # sigue consultando y ejecuta las tareas a medida que aparecen
```

`--dry-run` no clona nada ni inicia ningún agente, así que puedes repetirlo sin riesgo mientras ajustas
los filtros y el prompt.

## A dónde ir después

| Quiero... | Lee |
| --- | --- |
| Instalar Curupira y las CLI de agentes | [Instalación](installation.md) |
| Entender cada ajuste del archivo | [Configuración](configuration.md) |
| Elegir un trigger y ver un ejemplo mínimo | [Automatizaciones](automations.md) |
| Filtrar issues y pull requests | [Issues y pull requests de GitHub](github.md) |
| Trabajar desde una columna de un tablero de proyecto | [GitHub Projects](github-projects.md) |
| Escribir un prompt más inteligente (condiciones, bucles) | [Cómo escribir prompts](prompts.md) |
| Ver todos los campos que puede usar un prompt | [Referencia de campos del prompt](prompt-fields.md) |
| Copiar una configuración que funciona | [Recetas](recipes.md) |
| Elegir o ajustar el agente de código | [Proveedores y agentes](providers.md) |
| Usarlo día a día, leer logs, corregir errores | [Operaciones](operations.md) |
