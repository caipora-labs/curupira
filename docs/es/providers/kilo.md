# Kilo CLI

Instala Kilo con npm:

```bash
npm install -g @kilocode/cli
```

Autentícate con `kilo auth login` o configura las credenciales de un proveedor de modelos compatible en Kilo. Curupira no guarda, solicita ni gestiona credenciales; Kilo y sus
integraciones con proveedores se encargan de la autenticación.

Curupira invoca `kilo run --format json` y envía el mensaje de la tarea después de `--`. Los
eventos JSONL de Kilo incluyen un ID de sesión en cada registro, y las partes de texto usan la misma
forma `text`/`part.text` que OpenCode. Por eso Curupira usa el parser y el renderizador de sesión compartidos, y
reanuda una sesión guardada con `--session <session_id>`.

| Opción del perfil | Argumento nativo | Notas |
| --- | --- | --- |
| `model` | `--model <provider/model>` | Usa el identificador `provider/model` de Kilo. |
| `agent` | `--agent <agent>` | Nombre de un agente de Kilo existente. |
| `effort` | `--variant <effort>` | Variante de razonamiento específica del proveedor, como `high`, `max` o `minimal`. |
| `auto_approve` | `--auto` cuando es `true` | Peligroso: aprueba automáticamente los permisos que no se hayan denegado explícitamente. |
| ID de sesión | `--session <session_id>` | Lo añade Curupira al reanudar una tarea. |
| Mensaje de la tarea | `-- <message>` | El separador evita que los mensajes que empiezan con `-` se interpreten como flags. |

`effort` se traduce a `--variant`; el `--thinking` de Kilo solo muestra bloques de razonamiento y no se
usa como opción de esfuerzo de razonamiento. Sin `auto_approve`, Kilo rechaza las solicitudes de
permisos durante las ejecuciones sin interfaz en lugar de esperar una entrada interactiva. Deja
`auto_approve` desactivado a menos que ese comportamiento de permisos más amplio sea intencional.

::: curupira.agents.kilo.KiloCliProfile
