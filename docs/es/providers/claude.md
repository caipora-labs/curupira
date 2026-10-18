# Claude Code

Curupira ejecuta [Claude Code](https://docs.anthropic.com/en/docs/claude-code) en modo
print con salida JSON en streaming:

```text
claude -p --output-format stream-json --verbose [options] -- <prompt>
```

## Instalar e iniciar sesión { #install }

```sh
npm install -g @anthropic-ai/claude-code
claude   # inicia sesión una vez, de forma interactiva
```

Claude Code se encarga de la autenticación (una cuenta de Anthropic o `ANTHROPIC_API_KEY`).
Curupira nunca lee ni guarda credenciales.

## Opciones del perfil { #options }

| Opción | Argumento nativo | Notas |
| --- | --- | --- |
| `model` | `--model <model>` | Un alias como `sonnet` o un id de modelo completo. |
| `agent` | `--agent <agent>` | Un agente personalizado definido en Claude Code. |
| `effort` | `--effort <level>` | Nivel de esfuerzo de razonamiento. |
| `permission_mode` | `--permission-mode <mode>` | Por ejemplo `acceptEdits` o `plan`. Sin definir, se conserva el valor predeterminado de Claude Code. |
| `permission_prompts` | `--permission-prompts <value>` | Se pasa sin cambios. |

Las opciones sin definir no agregan ningún argumento. El prompt siempre va después de `--`,
así que un prompt que empieza con `-` no se interpreta como un flag.

## Ejemplo { #example }

```toml
[agents.profiles.claude]
provider = "claude"
model = "sonnet"
permission_mode = "acceptEdits"
```

## Sesiones { #sessions }

El id de sesión del stream JSON se guarda con la tarea. Una tarea interrumpida se reanuda
con `--resume <session_id>`.
