# Providers e agentes

O Curupira invoca cada ferramenta pela sua CLI nativa não interativa e salva os identificadores de sessão para retomar tarefas interrompidas. `model`, `effort` e `agent` são opcionais; opções não definidas são omitidas.

{{ agents_table("pt") }}

A página de cada provider descreve como as opções do profile são mapeadas para os argumentos nativos da CLI.

As substituições de permissão também são específicas de cada provider (`auto_approve` para OpenCode e Kilo,
`sandbox`/`auto_review` para Codex, `permission_mode`/`permission_prompts` para Claude Code,
`force`/`trust` para Cursor e `allow_all_tools`/`allow_tools`/`deny_tools` para a GitHub
Copilot CLI). Se omitidas, cada CLI mantém a sua política nativa.
