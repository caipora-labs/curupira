# Agentes de código

Curupira no incluye ningún modelo ni llama a una API de LLM. Inicia la CLI de agente de
código que ya usas, en modo no interactivo, dentro del worktree de la tarea. Tu inicio de
sesión, el acceso a modelos y los ajustes del agente se quedan en esa CLI.

## Agentes compatibles { #supported }

{{ agents_table("es") }}

Todos los adaptadores están integrados en Curupira. Agregar un agente es un cambio en el
propio Curupira, no un plugin.

## Perfiles { #profiles }

Un perfil es una forma con nombre de ejecutar un agente. Define todos los que necesites y
elige uno por automatización:

```toml
[agents.defaults]
profile = "claude"            # se usa cuando una automatización no define un perfil
timezone = "UTC"

[agents.profiles.claude]
provider = "claude"
model = "sonnet"

[agents.profiles.codex-high]
provider = "codex"
effort = "high"

[automations.review-ready-prs]
trigger_type = "plugins-py/github-pull-requests"
repository = "api"
repo = "acme/api"
profile = "codex-high"        # esta automatización usa Codex
prompt = "Review pull request #${pr_number}."
```

`model`, `agent` y `effort` son opcionales y significan lo mismo en todas partes; la página
de cada agente muestra el flag nativo en que se convierten. Una opción que omites no agrega
ningún argumento, así que la CLI conserva su propio valor predeterminado. Una opción que el
agente no admite es un error de configuración; no se ignora en silencio.

## Permisos { #permissions }

Las ejecuciones desatendidas no pueden responder solicitudes de permiso. Cada CLI tiene sus
propios interruptores, y Curupira solo pasa los que defines:

| Agente | Opciones |
| --- | --- |
| [Claude Code](providers/claude.md) | `permission_mode`, `permission_prompts` |
| [Codex](providers/codex.md) | `sandbox`, `auto_review` |
| [Cursor](providers/cursor.md) | `force`, `trust` |
| [Gemini CLI](providers/gemini.md) | `approval_mode`, `skip_trust` |
| [GitHub Copilot CLI](providers/copilot.md) | `allow_all_tools`, `allow_tools`, `deny_tools` |
| [Kilo CLI](providers/kilo.md) y [OpenCode](providers/opencode.md) | `auto_approve` |
| [pi](providers/pi.md) | `tools`, `exclude_tools`, `approve` |
| [Qwen Code](providers/qwen.md) | `approval_mode`, `max_session_turns` |

!!! warning "El texto de las tareas no es confiable"
    El texto de issues y pull requests termina en el prompt. Permisos amplios más un
    repositorio público permiten que cualquiera que pueda abrir una issue dirija al agente.
    Lee [Seguridad](github.md#security) antes de ampliar los permisos.

## Sesiones y límites { #sessions }

Curupira guarda el id de sesión de cada agente con la tarea y la reanuda si el proceso se
detiene antes de que la tarea termine. Cada ejecución está limitada por
`[settings].task_timeout_minutes` (por defecto `20`) y `[settings].max_output_bytes`.
