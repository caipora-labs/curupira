# Codex

Curupira ejecuta la [CLI de Codex](https://github.com/openai/codex) en modo no interactivo
con eventos JSON:

```text
codex exec [options] --json -- <prompt>
```

## Instalar e iniciar sesión { #install }

```sh
npm install -g @openai/codex
codex login
```

Codex se encarga de la autenticación (una cuenta de ChatGPT o una clave de API). Curupira
nunca lee ni guarda credenciales.

## Opciones del perfil { #options }

| Opción | Argumento nativo | Notas |
| --- | --- | --- |
| `model` | `--model <model>` | |
| `agent` | `--profile <name>` | Un perfil de tu `config.toml` de Codex. |
| `effort` | `--config model_reasoning_effort="<level>"` | Por ejemplo `low`, `medium`, `high`, `xhigh`. La disponibilidad depende del modelo. |
| `sandbox` | `--sandbox <mode>` | Por ejemplo `workspace-write`. Sin definir, se conserva la política de Codex. |
| `auto_review = true` | `--config approval_policy="on-request"` y `--config approvals_reviewer="auto_review"` | Permite que Codex revise sus propias solicitudes de aprobación. |

Las opciones sin definir no agregan ningún argumento.

## Ejemplo { #example }

```toml
[agents.profiles.codex]
provider = "codex"
model = "gpt-5-codex"
effort = "high"
sandbox = "workspace-write"
```

## Sesiones { #sessions }

El id del hilo de los eventos JSON se guarda con la tarea. Una tarea interrumpida se
reanuda con `codex exec resume <thread_id>`.
