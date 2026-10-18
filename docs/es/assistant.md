# Asistente de la TUI

`curu tui` integra un asistente de agente de código en un panel lateral. El agente de código se ejecuta
dentro del panel, así que no necesitas suspender la TUI.

## Atajos

| Tecla | Foco / contexto | Comportamiento |
| --- | --- | --- |
| `Ctrl+G` | En cualquier lugar | Abre o cierra el panel lateral del asistente (la mitad de la pantalla). Al cerrarlo se destruye el proceso hijo del PTY. |
| `F6` | Panel abierto | Alterna el foco del teclado entre el panel del asistente y el panel principal **sin** cerrar el panel. Mientras el PTY tiene el foco, de lo contrario absorbería las teclas del panel (`F1` ayuda, `F2` pausa, `F3` configuración, `F5` actualizar y `Tab`); `F6` devuelve esos atajos a la TUI principal, y `F6` de nuevo devuelve la escritura al agente. Se eligió porque las CLI de agentes de código rara vez la usan. |
| `Ctrl+C` | PTY del asistente con foco | Interrumpe el proceso hijo del agente (`SIGINT` de la terminal). **No** cierra la TUI. |
| `Ctrl+C` | TUI principal con foco | Cierra Curupira y destruye cualquier proceso hijo del asistente. |
| `Esc` | PTY del asistente con foco | Se reenvía al agente (no se usa para cerrar el panel). |
| `Esc` | Panel abierto, sin PTY (selector o error) | Cierra el panel lateral. |

El pie de página y la pantalla de ayuda (`F1`) muestran los mismos atajos.

## Elegir un agente

Cuando se abre el panel y `[assistant].agent` no está definido, Curupira lista todos los proveedores
de agentes de código registrados en `curupira.agents` (los integrados y los plugins instalados). Al elegir uno,
se escribe `agent` en la tabla `[assistant]` existente de tu TOML de configuración, en el mismo
lugar y con el mismo formato que los [ajustes del asistente de configuración](configuration.md#assistant).
El agente guardado se aplica la próxima vez que abras el panel; no necesitas reiniciar la
TUI. Al abrir el panel de nuevo se inicia una sesión interactiva nueva con ese agente.

Si `[assistant].model` es `"auto"` y el agente que eliges no tiene un modelo automático nativo,
Curupira elimina la clave `model` de `[assistant]` al guardar el nuevo agente. Un
modelo concreto se conserva.

!!! warning
    Guardar la elección del agente actualiza tu TOML de configuración en disco. Ese cambio de archivo activa
    la recarga en caliente de Curupira: las nuevas admisiones de tareas se pausan hasta que el trabajo en curso termina, y luego
    se recargan los ajustes y los feeds. Si quieres evitar esa pausa, es preferible elegir el agente cuando el orquestador esté inactivo.

Si no se puede escribir el archivo de configuración (no existe, es de solo lectura o tiene una forma TOML no compatible
para `assistant`, como una tabla en línea, una clave con puntos o un encabezado entre comillas), el panel muestra un
mensaje claro, deja el archivo intacto cuando la forma no es compatible y aun así aplica
la elección en memoria durante la sesión actual.

## Cómo empieza la sesión

1. El modelo viene de `[assistant].model`. Cuando esa clave no está definida, Curupira usa el
   modelo automático nativo del proveedor si el adaptador lo admite; de lo contrario se aplica el valor
   predeterminado de la propia CLI (con un aviso breve).
2. El comando interactivo se ejecuta en el directorio donde iniciaste `curu tui`.
3. Las claves de API de los proveedores no se reenvían a la terminal integrada; usa el
   inicio de sesión propio de la CLI del agente de código.

Si el ejecutable no está en el `PATH`, el panel muestra un mensaje claro de instalación en lugar de un
stack trace. Cerrar el panel (o salir de la TUI desde el panel principal) destruye
el proceso hijo. El cambio de tamaño de la ventana se propaga al PTY.

La persistencia solo reescribe una tabla `[assistant]` estándar sin comillas (reemplazo atómico en el
mismo directorio, conservando el modo del archivo, el estilo de salto de línea (LF o CRLF) y los comentarios de fin de línea
en las líneas `agent` / `model` existentes). Al eliminar `model` se borra esa línea sin dejar
una línea en blanco de más en la sección. No ejecuta un formateador completo de TOML; los demás comentarios y
tablas fuera de esa sección se dejan tal cual.

## Configuración relacionada

Consulta [`[assistant]`](configuration.md#assistant) para los campos `agent` y `model`.
Los adaptadores de agentes de código (incluidas las recetas de lanzamiento interactivo) están integrados en el núcleo
de Rust en `packages/curupira-core/src/agents/`; consulta [Extensiones de proceso](extensions.md) para ver el
límite de las fuentes de tareas.
