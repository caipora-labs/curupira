# Proveedores y agentes

Curupira invoca cada herramienta a través de su CLI nativa no interactiva y guarda los identificadores de sesión para reanudar las tareas interrumpidas. `model`, `effort` y `agent` son opcionales; las opciones sin definir se omiten.

{{ agents_table("es") }}

Cada página de proveedor describe cómo se traducen las opciones de su perfil a argumentos nativos de la CLI.

Los ajustes de permisos también son específicos de cada proveedor (`auto_approve` para OpenCode y Kilo,
`sandbox`/`auto_review` para Codex, `permission_mode`/`permission_prompts` para Claude Code,
`force`/`trust` para Cursor y `allow_all_tools`/`allow_tools`/`deny_tools` para GitHub
Copilot CLI). Si se omiten, cada CLI conserva su política nativa.
