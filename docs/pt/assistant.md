# Assistente da TUI

`curu tui` embute um assistente de agente de código em um painel lateral. O agente de código roda
dentro do painel, então você não precisa suspender a TUI.

## Atalhos

| Tecla | Foco / contexto | Comportamento |
| --- | --- | --- |
| `Ctrl+G` | Em qualquer lugar | Abre ou fecha o painel lateral do assistente (metade da tela). Fechar encerra o processo filho do PTY. |
| `F6` | Painel aberto | Alterna o foco do teclado entre o painel do assistente e o painel principal **sem** fechar o painel. Enquanto o PTY tem o foco, ele engoliria as teclas do painel (`F1` ajuda, `F2` pausa, `F3` configuração, `F5` atualizar e `Tab`); o `F6` devolve esses atalhos à TUI principal, e um novo `F6` devolve a digitação ao agente. Escolhido porque as CLIs de agentes de código raramente o usam. |
| `Ctrl+C` | PTY do assistente em foco | Interrompe o processo filho do agente (`SIGINT` do terminal). **Não** encerra a TUI. |
| `Ctrl+C` | TUI principal em foco | Encerra o Curupira e finaliza qualquer processo filho do assistente. |
| `Esc` | PTY do assistente em foco | Encaminhado ao agente (não é usado para fechar o painel). |
| `Esc` | Painel aberto, sem PTY (seletor ou erro) | Fecha o painel lateral. |

O rodapé e a tela de ajuda (`F1`) listam os mesmos atalhos.

## Escolhendo um agente

Quando o painel abre e `[assistant].agent` não está definido, o Curupira lista todos os providers de
agente de código registrados em `curupira.agents` (os embutidos e os plugins instalados). Ao escolher um,
o `agent` é gravado na tabela `[assistant]` existente do seu TOML de configurações, no mesmo
lugar e formato das [configurações do assistente](configuration.md#assistant).
O agente salvo vale na próxima vez que você abrir o painel; não é preciso reiniciar a
TUI. Abrir o painel novamente inicia uma nova sessão interativa com esse agente.

Se `[assistant].model` for `"auto"` e o agente escolhido não tiver model automático nativo,
o Curupira remove a chave `model` de `[assistant]` ao salvar o novo agente. Um model
concreto é mantido.

!!! warning
    Salvar a escolha do agente atualiza o seu TOML de configurações em disco. Essa mudança no arquivo dispara
    o hot-reload do Curupira: novas admissões de tarefas são pausadas até o trabalho em andamento terminar, e então
    as configurações e os feeds são recarregados. Prefira escolher o agente quando o orquestrador estiver ocioso,
    se quiser evitar essa pausa.

Se o arquivo de configuração não puder ser gravado (ausente, somente leitura ou com um formato TOML
de `assistant` não suportado, como tabela inline, chave com pontos ou cabeçalho entre aspas), o painel mostra uma
mensagem clara, deixa o arquivo intacto quando o formato não é suportado e ainda aplica
a escolha em memória durante a sessão atual.

## Como a sessão começa

1. O model vem de `[assistant].model`. Quando essa chave não está definida, o Curupira usa o
   model automático nativo do provider, se o adaptador o suportar; caso contrário, vale o padrão
   da própria CLI (com um aviso curto).
2. O comando interativo roda no diretório em que você iniciou `curu tui`.
3. As chaves de API dos providers não são repassadas ao terminal embutido; use o login da
   própria CLI do agente de código.

Se o executável não estiver no `PATH`, o painel mostra uma mensagem clara de instalação em vez de um stack
trace. Fechar o painel (ou sair da TUI pelo painel principal) encerra
o processo filho. O redimensionamento da janela é propagado ao PTY.

A persistência reescreve apenas uma tabela `[assistant]` padrão, sem aspas (substituição atômica no
mesmo diretório, preservando o modo do arquivo, o estilo de quebra de linha (LF ou CRLF) e os comentários de fim de linha
nas linhas `agent` / `model` existentes). Remover `model` apaga essa linha sem deixar
uma linha em branco extra na seção. Não é executado um pretty-printer completo de TOML; os outros comentários e
tabelas fora dessa seção permanecem como estão.

## Configuração relacionada

Veja [`[assistant]`](configuration.md#assistant) para os campos `agent` e `model`.
Os adaptadores de agentes de código (incluindo as receitas de execução interativa) são embutidos no core em Rust
em `packages/curupira-core/src/agents/`; veja [Extensões de processo](extensions.md) para o
limite das fontes de tarefas.
