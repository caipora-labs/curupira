# Plugins (legado)

Los hooks de Pluggy en proceso y los entry points `curupira.triggers` / `curupira.agents` han sido
**eliminados**.

- Las **fuentes de tareas** usan extensiones de proceso (JSON-RPC). Consulta
  [Extensiones de proceso](extensions.md) y la
  [especificación del protocolo](https://github.com/caipora-labs/curupira/blob/main/packages/curupira-core/PROTOCOL.md).
- Los **agentes de código** están integrados en la CLI de Rust. Configúralos con
  `[agents.profiles.*]` y la documentación de proveedores en [Proveedores](providers.md).
