# Painel no terminal

`curupira tui` (ou `curu tui`) abre um painel interativo e executa em segundo plano o mesmo
loop de despacho contínuo que `curupira run --watch`.

```sh
curupira tui
```

## Layout { #layout }

O `curupira tui` abre com o logo do Curupira centralizado na tela enquanto o despacho em
segundo plano começa. Depois de cerca de um segundo ele
dá lugar ao painel; pressione qualquer tecla ou clique para pular.

O painel tem duas colunas:

- **Barra lateral.** Cerca de um quinto da largura. O logo do Curupira e a versão, o botão
  `[ Home ]` e os repositórios cadastrados. Abaixo do nome de cada repositório ficam as
  sessões daquele repositório. Um ponto laranja ao lado do nome indica que um agente está
  atuando ali; um repositório sem sessão aparece esmaecido. Cada sessão mostra seu nome e
  seu agente.
- **Área de trabalho.** Um cabeçalho, o histórico da conversa e a entrada `curupira > ` fixa
  no rodapé. Na Home, o cabeçalho mostra `DEFAULT AGENT - (<diretório atual>)`. Com uma
  sessão aberta, mostra `ATTACHED: <sessão> - <agente>`.

O layout acompanha o tamanho do terminal. Abaixo de 48 × 12 o painel pede para ampliar o
terminal.

## Sessões { #sessions }

Cada tarefa iniciada pelo despacho em segundo plano abre uma sessão sob o repositório
(`[repositories.<alias>]`) na barra lateral. Os repositórios continuam listados quando não
têm sessão, para a barra mostrar onde um agente está atuando. A sessão usa
o nome que o agente de código dá à própria sessão: o OpenCode gera um título alguns segundos
depois de a sessão começar, e o painel lê esse título com `opencode session list`. Até lá, e
para agentes que não expõem títulos de sessão, ela leva o nome da issue ou do pull request
(`#223 bump paths-filter`) ou da automação, que também continua nos detalhes da sessão. O
ponto ao lado do repositório fica laranja enquanto algum agente dele está rodando, e não
aparece nos outros casos. O ponto ao lado da sessão mostra o estado dela: laranja enquanto o
agente roda, verde quando terminou, vermelho quando falhou.
`N running` ao lado do título `REPOSITORIES` conta as que estão rodando, quando a barra tem
largura para mostrar a contagem.

Abra uma sessão para acompanhar o agente ao vivo: a automação e o link, o prompt que ele
recebeu, as mensagens e as chamadas de ferramenta do agente conforme ele as informa e como a
tarefa terminou, com a própria mensagem de erro do agente quando falha. As sessões duram
enquanto o painel está aberto.

Uma mensagem digitada numa sessão é adicionada ao histórico e marcada como não enviada: o
painel ainda não consegue repassar mensagens a um agente em execução.

## Teclado { #keyboard }

| Tecla | Barra lateral em foco | Entrada em foco |
| --- | --- | --- |
| ++tab++ | Foca a entrada | Foca a barra lateral |
| ++up++ / ++down++ | Seleciona uma sessão | Rola o histórico |
| ++enter++ | Abre a sessão selecionada | Envia a mensagem |
| `h` | Volta para a Home | Digitado na entrada |
| `q` | Sai | Digitado na entrada |
| ++page-up++ / ++page-down++ | Rola o histórico | Rola o histórico |
| ++left++ / ++right++, ++home++ / ++end++, ++backspace++, ++delete++ | — | Edita a mensagem |
| ++esc++, ++ctrl+c++ | Sai | Sai |
| ++ctrl+l++ | Redesenha a tela | Redesenha a tela |

A entrada tem o foco quando o painel abre. Voltar para a Home mantém todas as sessões e seus
históricos.

## Mouse { #mouse }

- Clique em `[ Home ]` para voltar para a Home.
- Clique em uma sessão (em qualquer uma das duas linhas) para abri-la. O nome do
  repositório não é um botão.
- Clique na entrada para focá-la e posicionar o cursor.
- Role sobre a barra lateral para mover a lista de repositórios, ou sobre o histórico para ler
  mensagens anteriores. Rolar de volta até o fim volta a acompanhar novas mensagens.

Cliques em outros lugares não fazem nada.

## Despacho em segundo plano { #dispatch }

Enquanto o painel está aberto, o Curupira consulta todas as automações e executa as tarefas
exatamente como `run --watch`:

- Tarefas iniciadas, concluídas (`done`) e com falha aparecem pelo título no histórico da Home. O status no
  canto inferior direito mostra `dispatch idle`, quantas tarefas estão rodando ou
  `dispatch failed`.
- O painel obtém o `~/.curupira/dispatch.lock`, então não pode rodar ao lado de outro `run` ou
  `tui`.
- Sair para de admitir trabalho. Se ainda houver tarefas rodando, o Curupira informa quantas e
  espera por elas; pressione ++ctrl+c++ para interrompê-las.
- Um ++ctrl+c++ enviado como sinal (por exemplo, `kill -INT`) sai com status `130`. Sair com
  `q`, ++esc++ ou a tecla ++ctrl+c++ sai com status `0`, ou com o erro do despacho se alguma
  tarefa falhou.
- No Linux e no macOS, tudo o que é escrito no stderr enquanto o painel está aberto (logs,
  mensagens de extensões e de agentes) vai para `~/.curupira/logs/tui.log`, para não desenhar
  por cima da tela.

Tudo o que está em [Executando o Curupira](operations.md) sobre consultas, concorrência e códigos
de saída também se aplica ao `tui`.

## Sem terminal { #status-mode }

Quando stdin ou stdout não é um terminal (por exemplo, sob um gerenciador de serviços ou com a
saída redirecionada), o `tui` roda em **modo de status**. Ele imprime
`TUI: no terminal attached; running dispatch in status mode (Ctrl+C to stop)` no stderr e
depois se comporta exatamente como `run --watch`, imprimindo linhas `ok` e `fail`.

## Logo { #logo }

O logo é pixel art desenhada com caracteres de meio bloco (`▀`, `▄`) em cores de 24 bits: a
chama ao lado de uma marca `Curupira` leve. A splash o mostra centralizado no tamanho natural. A
barra lateral o mostra quando é larga o bastante, e a chama com o nome em texto caso contrário. O
painel não usa emojis. Terminais sem cores de 24 bits mostram cores aproximadas.

## A tabela `[assistant]` { #assistant }

`[assistant]` define o agente padrão mostrado na Home. O Curupira a lê e a valida:

```toml
[assistant]
agent = "claude"   # um nome de provider embutido, verificado por `curupira validate`
model = "sonnet"   # opcional
```

Um `agent` desconhecido é um erro de configuração. Veja
[Configuração](configuration.md#assistant) para a referência dos campos.
