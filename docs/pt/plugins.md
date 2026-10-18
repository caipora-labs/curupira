# Plugins (legado)

Os hooks Pluggy em processo e os entry points `curupira.triggers` / `curupira.agents` foram
**removidos**.

- **Fontes de tarefas** usam extensões de processo (JSON-RPC). Veja
  [Extensões de processo](extensions.md) e a
  [especificação do protocolo](https://github.com/caipora-labs/curupira/blob/main/packages/curupira-core/PROTOCOL.md).
- **Agentes de código** são embutidos na CLI em Rust. Configure-os com
  `[agents.profiles.*]` e a documentação dos providers em [Providers](providers.md).
