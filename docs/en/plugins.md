# Plugins (legacy)

In-process Pluggy hooks and `curupira.triggers` / `curupira.agents` entry points have been
**removed**.

- **Task sources** use process extensions (JSON-RPC). See
  [Process extensions](extensions.md) and the
  [protocol specification](https://github.com/caipora-labs/curupira/blob/main/packages/curupira-core/PROTOCOL.md).
- **Coding agents** are built into the Rust CLI. Configure them with
  `[agents.profiles.*]` and the provider docs under [Providers](providers.md).
