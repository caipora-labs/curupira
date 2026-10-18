# Gemini CLI

Curupira ejecuta Gemini CLI en modo `stream-json` no interactivo y reanuda las sesiones
con la opción nativa de Gemini `--resume <session_id>`.

## Instalación

Gemini CLI requiere Node.js 20 o superior. Instálalo globalmente con npm:

```bash
npm install -g @google/gemini-cli
```

## Autenticación

La autenticación corre por cuenta de Gemini CLI. Inicia sesión mediante su flujo de cuenta de Google, define
`GEMINI_API_KEY` o configura el entorno para Vertex AI. Curupira no lee,
guarda ni gestiona las credenciales del proveedor.

## Opciones de Curupira

Curupira traduce los campos del perfil de Gemini a estos argumentos nativos:

| Opción | Argumento nativo |
| --- | --- |
| `model` | `--model <model>` opcional |
| `approval_mode` | `--approval-mode <mode>` opcional: `default`, `auto_edit`, `yolo` o `plan` |
| `skip_trust` | `--skip-trust` cuando es `true` |
| `agent` | No compatible; se rechaza |
| `effort` | No compatible; se rechaza |

Cuando `approval_mode` no está definido, las ejecuciones sin interfaz usan la política de aprobación nativa de Gemini CLI.
Al definirlo se selecciona uno de los modos de aprobación explícitos de Gemini. **Advertencia:** definir
`approval_mode = "yolo"` desactiva las solicitudes de aprobación; úsalo solo cuando ese comportamiento sea
intencional. Curupira usa el valor `--approval-mode yolo` en lugar del flag obsoleto
`--yolo`.

El prompt se pasa como `--prompt=<message>`, de modo que los mensajes que empiezan con `-` se conservan como
texto del prompt. El identificador de sesión nativo de Gemini se captura de su evento `init`.

## Referencia del perfil

{% if page.url == "providers/gemini/" %}
::: curupira.agents.gemini.GeminiCliProfile
{% endif %}
