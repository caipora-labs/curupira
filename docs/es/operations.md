# Operaciones

Todos los comandos usan el mismo archivo de configuración y el mismo pipeline de ejecución. El alias corto `curu` acepta los mismos comandos.

```bash
curupira validate
curupira run
curupira run --dry-run
curupira run --size N
curupira run --watch
curupira tui
curupira --log-level DEBUG run --watch
```

- `validate` comprueba el TOML y las referencias sin ejecutar una automatización, llamar a CLI externas ni escribir estado. Termina con `0` si la configuración es válida y con `2` si hay errores de configuración.
- `run` vacía las tareas de automatización disponibles en ese momento a través del planificador compartido. Termina con `1` si una tarea ejecutada falló y con `0` en caso contrario. Antes de admitir una tarea, los elementos de GitHub se revalidan contra el estado actual del repositorio, de modo que el trabajo cerrado, los issues con un PR vinculado abierto y las sesiones recuperadas obsoletas no invocan la CLI del agente de código. `run` en modo de una sola pasada consulta juntos todos los feeds de las automatizaciones (si un feed falla, se registra en el log y los demás siguen aportando) y prueba el siguiente candidato cuando la revalidación descarta uno.
- `run --size N` limita un vaciado finito a un máximo de N tareas admitidas tras la revalidación. Las sesiones recuperadas cuentan para N; los candidatos descartados durante la revalidación no.
- `run --dry-run` previsualiza una tarea seleccionada sin reservar ni persistir ocurrencias de cron, sin hacer checkout de un repositorio y sin ejecutar nada.
- `run --watch` consulta todas las automatizaciones de forma continua hasta que lo interrumpas. Termina con `1` si una tarea ejecutada falló y con `0` en caso contrario.
- `tui` ejecuta el mismo planificador continuo que `run --watch` dentro de un panel interactivo de Textual (métricas, agentes activos y logs). Atajos: `Ctrl+G` abre o cierra el panel lateral del [asistente integrado](assistant.md), `F6` alterna el foco entre el asistente y el panel principal (el panel sigue abierto), `F1` ayuda, `F2` pausa o reanuda las admisiones, `F3` resumen de la configuración, `F5` actualiza las métricas, `Ctrl+C` sale desde la TUI principal (o interrumpe al agente cuando el PTY del asistente tiene el foco).
- El panel aloja al asistente en un panel lateral de medio ancho, respaldado por el widget reutilizable
  `PtyTerminal` (`curupira.tui.pty_terminal.PtyTerminal`). Compatibilidad de plataformas en
  la v1: Linux y macOS; Windows muestra un marcador de posición de no compatible. La emulación usa `pyte`
  (LGPL-3.0) como dependencia dinámica. Consulta [Asistente de la TUI](assistant.md) para el
  flujo de Ctrl+G y CONTRIBUTING.md para las tablas de rendimiento del PTY y las salvedades del ciclo de vida.

Mientras `run --watch` o `tui` están en ejecución, editar el archivo de configuración recarga los ajustes en caliente sin reiniciar el proceso. Se dejan de admitir tareas nuevas en cuanto el archivo cambia; las tareas que ya están en ejecución conservan sus snapshots resueltos y terminan. Cuando todas las tareas en curso se completan, Curupira recarga el TOML, reconstruye los feeds de descubrimiento y reanuda la consulta con la configuración más reciente. Si el archivo actualizado no es válido, las admisiones permanecen en pausa hasta que se guarde una configuración válida.

Selecciona otro TOML o cambia el nivel de log colocando las opciones globales antes del comando:

```bash
curupira --config ./settings-dev.toml validate
curupira --config ./settings-dev.toml run --watch
curupira --log-level DEBUG run --watch
```

`[settings].log_level` (valor predeterminado `INFO`) controla el nivel de detalle de la consola, del archivo y de la TUI
(`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). La opción global `--log-level` reemplaza
ese valor para un proceso y prevalece sobre los cambios del TOML recargados en caliente.

`run` y `run --watch` añaden registros de tareas a `~/.curupira/logs/curupira.log`. Los
fallos no capturados también escriben un informe detallado en `~/.curupira/logs/crashes/` (versión, plataforma,
traceback y contexto del comando) y habilitan volcados de `faulthandler` en
`~/.curupira/logs/faulthandler.log`, sin importar `log_level`. Las sesiones interrumpidas por
reinicios del proceso se guardan en la base de datos de estado; `run --watch` reanuda las sesiones guardadas
tras el reinicio. Los fallos transitorios de `gh` se reintentan con backoff. Los fallos de autenticación, configuración,
formato de salida y tareas del agente no se reintentan automáticamente.
