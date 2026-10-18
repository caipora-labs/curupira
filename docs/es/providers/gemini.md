# Gemini CLI

Curupira ejecuta [Gemini CLI](https://github.com/google-gemini/gemini-cli) en modo no
interactivo con salida JSON en streaming:

```text
gemini --output-format stream-json [options] --prompt=<prompt>
```

## Instalar e iniciar sesión { #install }

Gemini CLI necesita Node.js 20 o posterior.

```sh
npm install -g @google/gemini-cli
gemini   # inicia sesión una vez con tu cuenta de Google
```

También puedes definir `GEMINI_API_KEY` o configurar Vertex AI. Gemini CLI se encarga de la
autenticación; Curupira nunca lee ni guarda credenciales.

## Opciones del perfil { #options }

| Opción | Argumento nativo | Notas |
| --- | --- | --- |
| `model` | `--model <model>` | `auto` deja que Gemini elija. |
| `approval_mode` | `--approval-mode <mode>` | `default`, `auto_edit`, `yolo` o `plan`. Sin definir, se conserva la política de Gemini. |
| `skip_trust = true` | `--skip-trust` | Omite la verificación de confianza de la carpeta. |
| `agent` | — | No se admite; se rechaza. |
| `effort` | — | No se admite; se rechaza. |

!!! warning "`yolo` lo aprueba todo"
    `approval_mode = "yolo"` desactiva las solicitudes de aprobación. Curupira pasa
    `--approval-mode yolo` en lugar del flag obsoleto `--yolo`.

El prompt se pasa como `--prompt=<prompt>`, así que un prompt que empieza con `-` sigue
siendo texto.

## Ejemplo { #example }

```toml
[agents.profiles.gemini]
provider = "gemini"
model = "auto"
approval_mode = "auto_edit"
```

## Sesiones { #sessions }

El id de sesión viene del evento `init` de Gemini y se guarda con la tarea. Una tarea
interrumpida se reanuda con `--resume <session_id>`.
