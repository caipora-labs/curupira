# pi

Curupira ejecuta pi en modo JSON con `pi --mode json ... -- <message>`. Un nuevo ID de sesión
proviene del encabezado de sesión JSONL de pi y se reanuda con `--session <id>`. pi agrupa las
sesiones por directorio de trabajo; los worktrees de tarea deterministas de Curupira mantienen las ejecuciones reanudadas
en el mismo directorio de proyecto.

## Instalación

Instala pi globalmente con npm. Requiere Node.js 22.19.0 o posterior.

```sh
npm install -g @earendil-works/pi-coding-agent
node --version
```

Autentica pi con las variables de entorno de clave de API del proveedor de modelos seleccionado o usa el
comando `/login` de pi. Curupira no recopila, guarda ni reenvía credenciales; el proceso de pi
usa el entorno y la autenticación configurados del usuario.

## Opciones del perfil

| Opción de Curupira | Argumento de pi | Notas |
| --- | --- | --- |
| `model` | `--model <model>` | Patrón de modelo exacto o aproximado; puede incluir `provider/id`. |
| `model_provider` | `--provider <provider>` | Requiere `model`; evita una colisión de nombres con el discriminador `provider` de Curupira. |
| `effort` | `--thinking <level>` | `off`, `minimal`, `low`, `medium`, `high`, `xhigh` o `max`. |
| `tools` | `--tools a,b` | Lista de permitidos, separada por comas, de las herramientas que pi puede usar. |
| `exclude_tools` | `--exclude-tools a,b` | Herramientas a excluir, separadas por comas. |
| `approve = true` | `--approve` | Confiar explícitamente en el proyecto actual para este proceso. |
| `approve = false` | `--no-approve` | No confiar explícitamente en el proyecto actual para este proceso. |
| `approve` omitido | *(sin argumento)* | Deja sin cambios el comportamiento de confianza del proyecto configurado en pi. |

pi no pide aprobación antes de cada llamada a una herramienta, y su modo JSON no puede mostrar el
aviso de confianza del proyecto. Cuando la confianza predeterminada configurada es `ask`, pi omite los recursos
protegidos del proyecto a menos que la invocación tome una decisión explícita. Define `approve` solo cuando
esa decisión de confianza a nivel de proyecto sea intencional. Usa `tools` para limitar la lista de permitidos,
`exclude_tools` para quitar herramientas específicas y los worktrees por tarea de Curupira para aislar los
cambios del repositorio. pi no tiene una opción nativa de agente personalizado, así que los perfiles de Curupira no
aceptan `agent`.

Curupira añade cada prompt después de `--`, de modo que un guion inicial se pasa como texto del prompt. pi
también trata `@path` como una inclusión de archivo: un prompt que empiece con `@` puede leerse como una referencia
de archivo en lugar de texto normal.

```toml
[coding_agents.profiles.pi]
provider = "pi"
model = "anthropic/claude-sonnet-4"
model_provider = "anthropic"
effort = "high"
tools = ["read", "edit", "write"]
exclude_tools = ["bash"]
# approve = true # confiar explícitamente en los recursos del proyecto para este proceso
```

El identificador de sesión que emite pi se persiste y se reanuda en el mismo worktree de tarea
determinista. Curupira usa el evento final `message_end` del asistente y une sus bloques de texto;
el contenido de razonamiento y de llamadas a herramientas no se muestra como resultado de la tarea.

::: curupira.agents.pi.PiCliProfile
