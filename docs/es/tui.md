# Panel en la terminal

`curupira tui` (o `curu tui`) ejecuta el mismo ciclo continuo de despacho que
`curupira run --watch`, iniciado desde el punto de entrada del panel.

```sh
curupira tui
```

## Qué hace hoy { #status-mode }

La CLI de Rust ejecuta el panel en **modo de estado**:

- Imprime `TUI: running dispatch dashboard (status mode); press Ctrl+C to stop` en stderr.
- Consulta cada automatización y ejecuta las tareas exactamente como `run --watch`,
  imprimiendo líneas `ok` y `fail` a medida que las tareas terminan.
- Toma `~/.curupira/dispatch.lock`, así que no puede ejecutarse junto a otro `run` o `tui`.
- ++ctrl+c++ deja de admitir trabajo y sale con el código `130`.

Todo lo que dice [Ejecutar Curupira](operations.md) sobre consultas, concurrencia y
códigos de salida también se aplica a `tui`.

!!! note "Los paneles interactivos todavía no están disponibles"
    El panel todavía no tiene paneles ni asistente. Hasta que los tenga, `run --watch` y
    `tui` se comportan igual.

## La tabla `[assistant]` { #assistant }

`[assistant]` está reservada para el asistente interactivo. Curupira ya la lee y la valida,
así que un archivo escrito hoy seguirá funcionando cuando llegue el panel:

```toml
[assistant]
agent = "claude"   # un nombre de proveedor integrado, verificado por `curupira validate`
model = "sonnet"   # opcional
```

Un `agent` desconocido es un error de configuración. Consulta
[Configuración](configuration.md#assistant) para la referencia de campos.
