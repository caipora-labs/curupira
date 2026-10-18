# Painel no terminal

`curupira tui` (ou `curu tui`) executa o mesmo loop de despacho contínuo que
`curupira run --watch`, iniciado a partir do ponto de entrada do painel.

```sh
curupira tui
```

## O que ele faz hoje { #status-mode }

A CLI em Rust executa o painel em **modo de status**:

- Ela imprime `TUI: running dispatch dashboard (status mode); press Ctrl+C to stop` no stderr.
- Ela consulta todas as automações e executa as tarefas exatamente como `run --watch`, imprimindo linhas `ok` e
  `fail` à medida que as tarefas terminam.
- Ela obtém o `~/.curupira/dispatch.lock`, então não pode rodar ao lado de outro `run` ou `tui`.
- ++ctrl+c++ para de admitir trabalho e sai com status `130`.

Tudo o que está em [Executando o Curupira](operations.md) sobre consultas, concorrência e códigos
de saída também se aplica ao `tui`.

!!! note "Os painéis interativos ainda não estão disponíveis"
    O painel ainda não tem painéis nem assistente. Até que tenha, `run --watch` e `tui` se
    comportam da mesma forma.

## A tabela `[assistant]` { #assistant }

`[assistant]` é reservada para o assistente interativo. O Curupira já a lê e
valida, então um arquivo escrito hoje continua funcionando quando o painel chegar:

```toml
[assistant]
agent = "claude"   # um nome de provider embutido, verificado por `curupira validate`
model = "sonnet"   # opcional
```

Um `agent` desconhecido é um erro de configuração. Veja
[Configuração](configuration.md#assistant) para a referência dos campos.
