# Operação

Todos os comandos usam o mesmo arquivo de configuração e o mesmo pipeline de execução. O alias curto `curu` aceita os mesmos comandos.

```bash
curupira validate
curupira run
curupira run --dry-run
curupira run --size N
curupira run --watch
curupira tui
curupira --log-level DEBUG run --watch
```

- `validate` verifica o TOML e as referências sem executar uma automação, chamar CLIs externas nem gravar estado. Sai com `0` para configuração válida e `2` para erros de configuração.
- `run` esgota as tarefas de automação atualmente disponíveis por meio do scheduler compartilhado. Sai com `1` se uma tarefa executada falhou; caso contrário, `0`. Antes de admitir uma tarefa, os itens do GitHub são revalidados contra o estado atual do repositório, para que trabalho já fechado, issues com um PR vinculado aberto e sessões recuperadas obsoletas não invoquem a CLI do agente de código. O `run` de execução única consulta todos os feeds de automação juntos (um feed que falha é registrado no log; os outros continuam contribuindo) e tenta o próximo candidato quando a revalidação descarta um.
- `run --size N` limita um esgotamento finito a no máximo N tarefas admitidas após a revalidação. Sessões recuperadas contam para N; candidatos descartados durante a revalidação não.
- `run --dry-run` mostra uma prévia de uma tarefa selecionada sem reservar nem persistir ocorrências de cron, sem fazer checkout de um repositório e sem executar.
- `run --watch` consulta todas as automações continuamente até ser interrompido. Sai com `1` se uma tarefa executada falhou; caso contrário, `0`.
- `tui` executa o mesmo scheduler contínuo do `run --watch` dentro de um painel interativo em Textual (métricas, agentes ativos e logs). Atalhos: `Ctrl+G` abre/fecha o painel lateral do [assistente embutido](assistant.md), `F6` alterna o foco entre o assistente e o painel principal (o painel continua aberto), `F1` ajuda, `F2` pausa/retoma admissões, `F3` resumo da configuração, `F5` atualiza as métricas, `Ctrl+C` sai da TUI principal (ou interrompe o agente quando o PTY do assistente tem o foco).
- O painel hospeda o assistente em um painel lateral de meia largura, sustentado pelo widget reutilizável
  `PtyTerminal` (`curupira.tui.pty_terminal.PtyTerminal`). Suporte de plataformas na
  v1: Linux e macOS; o Windows mostra um aviso de não suportado. A emulação usa `pyte`
  (LGPL-3.0) como dependência dinâmica. Veja [Assistente da TUI](assistant.md) para o
  fluxo com Ctrl+G e CONTRIBUTING.md para as tabelas de throughput do PTY e as ressalvas do ciclo de vida.

Enquanto `run --watch` ou `tui` está em execução, editar o arquivo de configuração recarrega as configurações a quente, sem reiniciar o processo. Novas tarefas deixam de ser admitidas assim que o arquivo muda; as tarefas que já estão rodando mantêm seus snapshots resolvidos e terminam. Depois que todas as tarefas em andamento são concluídas, o Curupira recarrega o TOML, reconstrói os feeds de descoberta e retoma a consulta com a configuração mais recente. Se o arquivo atualizado for inválido, a admissão permanece pausada até que uma configuração válida seja salva.

Selecione outro TOML ou substitua o nível de log colocando as opções globais antes do comando:

```bash
curupira --config ./settings-dev.toml validate
curupira --config ./settings-dev.toml run --watch
curupira --log-level DEBUG run --watch
```

`[settings].log_level` (padrão `INFO`) controla a verbosidade do console, do arquivo e da TUI
(`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). A flag global `--log-level` substitui
esse valor em um único processo e prevalece sobre mudanças do TOML recarregadas a quente.

`run` e `run --watch` acrescentam registros das tarefas em `~/.curupira/logs/curupira.log`. Falhas
não tratadas também gravam um relatório detalhado em `~/.curupira/logs/crashes/` (versão, plataforma,
traceback e contexto do comando) e habilitam dumps do `faulthandler` em
`~/.curupira/logs/faulthandler.log`, independentemente de `log_level`. As sessões interrompidas por
reinícios do processo ficam armazenadas no banco de estado; `run --watch` retoma as sessões salvas
após o reinício. Falhas transitórias do `gh` são repetidas com backoff. Falhas de autenticação, configuração,
formato de saída e tarefas do agente não são repetidas automaticamente.
