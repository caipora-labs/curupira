# Primeros pasos

Esta página toma unos cinco minutos. Al final, Curupira vigila un repositorio y entrega a
Claude Code cada issue con el label `agent-ready`. Cambia el agente o el label por los tuyos.

Necesitas [Git](https://git-scm.com/), la [CLI de GitHub](https://cli.github.com/) (`gh`) y
una CLI de agente de código con la sesión ya iniciada. [Instalación](installation.md) cubre
todas las plataformas y opciones.

## 1. Instala e inicia sesión

=== "uv"

    ```sh
    uv tool install curupira
    gh auth login
    ```

=== "pip"

    ```sh
    pip install curupira
    gh auth login
    ```

=== "npm"

    ```sh
    npm install -g @caipora/curupira
    gh auth login
    ```

El conector de GitHub es un [plugin](plugins.md) que Curupira inicia con `uvx`, así que
también necesitas [uv](https://docs.astral.sh/uv/) en el `PATH`. No se instala nada más de
antemano.

## 2. Escribe `~/.curupira/settings.toml`

```toml
[repositories.api]
remote = "https://github.com/acme/api.git"   # (1)!

[agents.defaults]
profile = "claude"
timezone = "UTC"

[agents.profiles.claude]
provider = "claude"                           # (2)!

[plugins.plugins-py]                          # (3)!
type = "uvx"
args = ["--from", "curupira-plugins", "curupira-plugins"]

[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"     # (4)!
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
prompt = """
Resolve issue #${issue_number}: ${issue_title}

${issue_body}
"""
```

1.  Donde trabaja el agente. Curupira lo clona una vez y le da a cada tarea su propio worktree.
2.  Cualquier [agente compatible](providers.md): `codex`, `gemini`, `opencode` y más.
3.  Registra el conector de GitHub con el alias `plugins-py`. Los demás conectores se
    registran de la misma forma.
4.  `<alias>/<trigger>`: el trigger de issues del conector registrado arriba. `repo` y
    `labels` son sus filtros, y `${issue_number}` y los demás campos completan el prompt.

## 3. Valídalo, previsualízalo y ejecútalo

```sh
curupira validate      # ¿el archivo es correcto?
curupira run --dry-run # qué tarea se ejecutaría y el prompt exacto que recibe el agente
curupira run --watch   # sigue consultando y ejecuta las tareas a medida que aparecen
```

!!! tip "Puedes repetirlo sin riesgo"
    `--dry-run` no clona nada ni inicia ningún agente. Úsalo mientras ajustas los filtros y
    el prompt.

## Próximos pasos

- [Cómo funciona](concepts.md): qué pasa entre la issue y el agente.
- [Cómo escribir prompts](prompts.md): condiciones, bucles y todos los campos que puedes usar.
- [Recetas](recipes.md): revisiones de pull requests, Dependabot, columnas de tableros y cron.
- [Ejecutar Curupira](operations.md): salida, códigos de salida y sesiones.
