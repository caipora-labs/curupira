# Executando o Curupira

Todos os comandos leem o mesmo arquivo de configuração e usam o mesmo pipeline de despacho. O
alias curto `curu` aceita todos os comandos.

## Comandos { #commands }

| Comando | O que faz |
| --- | --- |
| `curupira validate` | Verifica o TOML, as referências, os plugins e os prompts. Não executa nenhuma automação e não grava estado. |
| `curupira run` | Executa as tarefas disponíveis agora e depois sai. |
| `curupira run --size N` | O mesmo, mas admite no máximo `N` tarefas. |
| `curupira run --dry-run` | Imprime a primeira tarefa que rodaria e o seu prompt renderizado. Não clona nada e não inicia nenhum agente. |
| `curupira run --watch` | Continua consultando e executando tarefas até ser interrompido. |
| `curupira tui` | O loop contínuo a partir do ponto de entrada do [painel no terminal](tui.md). |
| `curupira plugins …` | Lista e inspeciona os [plugins e triggers](extensions.md#manage) disponíveis. |

`--dry-run`, `--watch` e `--size` não podem ser combinados; o Curupira sai com status `2`
se você tentar.

As opções globais vêm antes do comando:

```sh
curupira --config ./settings-dev.toml validate
curupira --config ./settings-dev.toml run --watch
curupira --log-level DEBUG run --watch
curupira --version
```

O padrão de `--config` é `~/.curupira/settings.toml`. `--log-level` substitui
`[settings].log_level` em um único processo (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).

## Saída { #output }

`run` imprime uma linha por tarefa concluída, separada por tab:

```text
ok      resolve-ready-issues:acme/api:plugins-py/github-issues:9c1e…
fail    review-ready-prs:acme/api:plugins-py/github-pull-requests:41ad…  agent exited 1: …
```

A segunda coluna é a identidade da tarefa: automação, repositório, trigger e um hash dos
campos do item. As linhas `ok` vão para o stdout e as linhas `fail` para o stderr, então você pode
redirecioná-las separadamente.

`run --dry-run` imprime a identidade e o prompt exato que o agente receberia:

```text
dry-run resolve-ready-issues:acme/api:plugins-py/github-issues:9c1e…
--- prompt ---
Resolve issue #128: Retry flaky webhook deliveries
…
--- end prompt ---
```

## Códigos de saída { #exit-codes }

| Código | Significado |
| --- | --- |
| `0` | Sucesso. Para `run`, todas as tarefas executadas terminaram `ok`. |
| `1` | Pelo menos uma tarefa falhou, ou um erro de plugin ou de execução interrompeu o `run`. |
| `2` | Erro de configuração (TOML inválido, referência desconhecida, flags conflitantes). |
| `130` | Interrompido com ++ctrl+c++. |

## Agendamento { #scheduling }

- Até `[settings].max_active_tasks` tarefas rodam ao mesmo tempo (padrão `1`).
- No modo `--watch`, o Curupira consulta todas as automações a cada
  `[settings.polling].poll_interval_seconds` (padrão `30`).
- Uma tarefa que terminou `ok` fica registrada no banco de estado e nunca roda de novo.
- Uma tarefa que falha não é repetida no mesmo processo. O próximo `run` (ou um `--watch`
  reiniciado) tenta de novo.
- Cada execução do agente é limitada a `[settings].task_timeout_minutes` (padrão `20`).

## Um processo por vez { #lock }

`run` e `tui` mantêm o `~/.curupira/dispatch.lock` enquanto trabalham. Um segundo processo que
tenta despachar falha imediatamente em vez de concorrer com o primeiro. `validate`, `run --dry-run` e
`plugins` não obtêm o lock.

## Retomando sessões { #resume }

Quando um agente anuncia um id de sessão (ou o Curupira atribui um), ele é salvo com a tarefa.
Se o processo parar antes de a tarefa terminar, o próximo `run` retoma essa sessão e pede
ao agente que continue o trabalho anterior em vez de começar do zero. A sessão é removida
quando a tarefa termina `ok`.

## Alterando a configuração { #reload }

O Curupira lê a configuração uma vez quando um comando começa. Depois de editar o
`settings.toml`, execute `curupira validate` e então reinicie `run --watch` ou `tui` para aplicar
a mudança. As tarefas em execução terminam com as configurações com que começaram.
