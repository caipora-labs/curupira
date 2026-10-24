# Panel en la terminal

`curupira tui` (o `curu tui`) abre un panel interactivo y ejecuta en segundo plano el mismo
ciclo continuo de despacho que `curupira run --watch`.

```sh
curupira tui
```

## Diseño { #layout }

`curupira tui` se abre con el logo de Curupira centrado en la pantalla mientras arranca el
despacho en segundo plano. Después de alrededor de un
segundo da paso al panel; pulsa cualquier tecla o haz clic para saltarlo.

El panel tiene dos columnas:

- **Barra lateral.** Alrededor de una quinta parte del ancho. El logo de Curupira y la versión, el botón
  `[ Home ]` y los repositorios registrados. Debajo del nombre de cada repositorio están las
  sesiones de ese repositorio. Un punto naranja junto al nombre indica que un agente está
  actuando ahí; un repositorio sin sesión aparece atenuado. Cada sesión muestra su nombre y
  su agente.
- **Área de trabajo.** Un encabezado, el historial de la conversación y la entrada
  `curupira > ` fija al pie. En Home, el encabezado muestra
  `DEFAULT AGENT - (<directorio actual>)`. Con una sesión abierta, muestra
  `ATTACHED: <sesión> - <agente>`.

El diseño se adapta al tamaño de la terminal. Por debajo de 48 × 12 el panel pide agrandar la
terminal.

## Sesiones { #sessions }

Cada tarea que inicia el despacho en segundo plano abre una sesión bajo su repositorio
(`[repositories.<alias>]`) en la barra lateral. Los repositorios siguen listados cuando no
tienen sesión, para que la barra muestre dónde está actuando un agente. La sesión toma
el nombre que el agente de código le da a su sesión: OpenCode genera un título unos segundos
después de que la sesión empieza, y el panel lee ese título con `opencode session list`. Hasta
entonces, y para agentes que no exponen títulos de sesión, lleva el nombre de su issue o pull
request (`#223 bump paths-filter`) o de su automatización, que también sigue en los detalles de
la sesión. El punto junto al repositorio es naranja mientras uno de sus agentes se ejecuta, y
no aparece en los demás casos. El punto junto a la sesión muestra el estado de esa sesión:
naranja mientras el agente se ejecuta, verde cuando terminó, rojo cuando
falló. `N running` junto al título `REPOSITORIES` cuenta las que están en ejecución, cuando la
barra es lo bastante ancha para mostrar la cuenta.

Abre una sesión para seguir a su agente en vivo: la automatización y el enlace, el prompt que
recibió, los mensajes y las llamadas a herramientas del agente a medida que los informa y cómo
terminó, con el propio mensaje de error del agente cuando falla. Las sesiones duran mientras el
panel está abierto.

Un mensaje que escribes en una sesión se agrega a su historial y se marca como no enviado: el
panel todavía no puede pasar mensajes a un agente en ejecución.

## Teclado { #keyboard }

| Tecla | Barra lateral con foco | Entrada con foco |
| --- | --- | --- |
| ++tab++ | Enfoca la entrada | Enfoca la barra lateral |
| ++up++ / ++down++ | Selecciona una sesión | Desplaza el historial |
| ++enter++ | Abre la sesión seleccionada | Envía el mensaje |
| `h` | Vuelve a Home | Se escribe en la entrada |
| `q` | Sale | Se escribe en la entrada |
| ++page-up++ / ++page-down++ | Desplaza el historial | Desplaza el historial |
| ++left++ / ++right++, ++home++ / ++end++, ++backspace++, ++delete++ | — | Edita el mensaje |
| ++esc++, ++ctrl+c++ | Sale | Sale |
| ++ctrl+l++ | Redibuja la pantalla | Redibuja la pantalla |

La entrada tiene el foco cuando se abre el panel. Volver a Home conserva todas las sesiones y
sus historiales.

## Ratón { #mouse }

- Haz clic en `[ Home ]` para volver a Home.
- Haz clic en una sesión (en cualquiera de sus dos líneas) para abrirla. El nombre del
  repositorio no es un botón.
- Haz clic en la entrada para enfocarla y colocar el cursor.
- Desplázate sobre la barra lateral para mover la lista de repositorios, o sobre el historial para
  leer mensajes anteriores. Al volver al final, se siguen de nuevo los mensajes nuevos.

Los clics en otros lugares no hacen nada.

## Despacho en segundo plano { #dispatch }

Mientras el panel está abierto, Curupira consulta cada automatización y ejecuta las tareas
exactamente como `run --watch`:

- Las tareas iniciadas, terminadas (`done`) y fallidas aparecen por título en el historial de Home. El
  estado en la esquina inferior derecha muestra `dispatch idle`, cuántas tareas se están
  ejecutando o `dispatch failed`.
- El panel toma `~/.curupira/dispatch.lock`, así que no puede ejecutarse junto a otro `run` o
  `tui`.
- Salir deja de admitir trabajo. Si todavía hay tareas en ejecución, Curupira indica cuántas y
  las espera; pulsa ++ctrl+c++ para detenerlas.
- Un ++ctrl+c++ enviado como señal (por ejemplo, `kill -INT`) sale con el código `130`. Salir
  con `q`, ++esc++ o la tecla ++ctrl+c++ sale con el código `0`, o con el error del despacho si
  alguna tarea falló.
- En Linux y macOS, todo lo que se escribe en stderr mientras el panel está abierto (logs,
  mensajes de extensiones y de agentes) va a `~/.curupira/logs/tui.log`, para que no se dibuje
  encima de la pantalla.

Todo lo que dice [Ejecutar Curupira](operations.md) sobre consultas, concurrencia y
códigos de salida también se aplica a `tui`.

## Sin terminal { #status-mode }

Cuando stdin o stdout no es una terminal (por ejemplo, bajo un gestor de servicios o con la
salida redirigida), `tui` se ejecuta en **modo de estado**. Imprime
`TUI: no terminal attached; running dispatch in status mode (Ctrl+C to stop)` en stderr y luego
se comporta exactamente como `run --watch`, imprimiendo líneas `ok` y `fail`.

## Logo { #logo }

El logo es pixel art dibujado con caracteres de medio bloque (`▀`, `▄`) en color de 24 bits: la
llama junto a una marca `Curupira` ligera. La pantalla de inicio lo muestra centrado en su
tamaño natural. La barra lateral lo muestra cuando es lo bastante ancha, y la llama con el
nombre como texto en caso contrario. El panel no usa emojis. Las terminales sin color de 24 bits
muestran colores aproximados.

## La tabla `[assistant]` { #assistant }

`[assistant]` define el agente predeterminado que se muestra en Home. Curupira la lee y la
valida:

```toml
[assistant]
agent = "claude"   # un nombre de proveedor integrado, verificado por `curupira validate`
model = "sonnet"   # opcional
```

Un `agent` desconocido es un error de configuración. Consulta
[Configuración](configuration.md#assistant) para la referencia de campos.
