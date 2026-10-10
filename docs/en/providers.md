# Providers and agents

Curupira invokes each tool through its non-interactive native CLI and saves session identifiers to resume interrupted tasks. `model`, `effort`, and `agent` are optional; unset options are omitted.

{{ providers_table() }}

Each provider page describes how its profile options map to native CLI arguments.

Permission overrides are also provider-specific (`auto_approve` for OpenCode and Kilo,
`sandbox`/`auto_review` for Codex, `permission_mode`/`permission_prompts` for Claude Code,
and `force`/`trust` for Cursor). If omitted, each CLI keeps its native policy.
