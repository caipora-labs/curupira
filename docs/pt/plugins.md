# Plugins

Plugins adicionam novas fontes de automação (tipos de trigger) sem alterar o Curupira. Um
plugin é uma distribuição Python comum, instalada junto com o Curupira, que declara um
entry point por trigger. As automações do plugin ficam no mesmo arquivo TOML, são
validadas quando a configuração é carregada e passam pelo mesmo agendamento, checkout e
execução do coding agent que os triggers embutidos.

O código de um plugin roda dentro do processo do Curupira assim que ele é descoberto.
Instale apenas distribuições em que você confia.

## Usando um plugin

Instale o plugin no mesmo ambiente do Curupira e confira se ele foi carregado:

```bash
uv tool install curupira --with curupira-tickets
curu plugins list
```

`curu plugins list` mostra cada tipo de trigger, a distribuição que o fornece e os
placeholders de prompt que ele adiciona. Configure a automação com esse `trigger_type` e
as opções documentadas pelo plugin:

```toml
[coding_agents.automations.ops-tickets]
trigger_type = "ticket"
repo = "acme/api"
project = "OPS"
prompt = "Corrija ${ticket_key} (${ticket_priority}) em ${repo}"
```

`curu validate` verifica as opções e os placeholders do plugin do mesmo jeito que faz com
os embutidos. Se um plugin não puder ser importado, todo comando que carrega a
configuração para com um `Configuration error` que informa o entry point e a distribuição.

## Escrevendo um plugin

Um plugin fornece três peças, todas importadas de `curupira.plugins`:

1. Um modelo de configuração que estende `AutomationConfigurationBase` e define o padrão
   de `trigger_type` igual ao tipo do plugin. Ele herda `repo`, `path`, `setup_script`,
   `checkout`, `prompt` e `profile`, e acrescenta as opções do plugin como campos e
   validadores Pydantic.
2. Um `TaskSource`, que transforma uma consulta em objetos `Task`. Use `PollingTaskFeed`
   em volta dele para ganhar deduplicação e backoff sem esforço.
3. Um `Trigger`, que liga o modelo de configuração, os placeholders de prompt e o feed.

O exemplo completo de código está na [página em inglês](../en/plugins.md#writing-a-plugin);
os nomes de classes e campos são os mesmos.

Registre o trigger no `pyproject.toml` do plugin. O entry point pode apontar para a
subclasse de `Trigger` (instanciada sem argumentos) ou para uma instância pronta:

```toml
[project]
name = "curupira-tickets"
dependencies = ["curupira"]

[project.entry-points."curupira.triggers"]
ticket = "curupira_tickets:TicketTrigger"
```

### Contrato

| Membro | Obrigatório | Função |
| --- | --- | --- |
| `trigger_type` | Sim | Valor usado em `trigger_type`; precisa ser único entre embutidos e plugins. |
| `configuration_model` | Sim | Modelo Pydantic da tabela da automação. |
| `prompt_fields()` | Sim | Placeholders que o trigger adiciona aos comuns. |
| `prompt_context(task)` | Sim | Valores desses placeholders. |
| `build_feed(automation, dependencies)` | Sim | Feed que descobre as tarefas. |
| `validate_task(task)` | Não | Rejeita snapshots de tarefa que o trigger não poderia ter gerado. |
| `create_version_control(runner)` | Não | Mecanismo de clone dos repositórios; `None` mantém o `gh repo clone`. |
| `on_task_started(task, state)` | Não | Roda logo antes de o coding agent começar. |
| `on_task_finished(task, state)` | Não | Libera estado depois que o agente termina; o padrão apaga a sessão retomável, então chame `super()` ao sobrescrever. |
| `api_version` | Não | Versão da API de plugins que o plugin usa; o padrão é o `PLUGIN_API_VERSION` do Curupira em execução. Defina explicitamente para falhar cedo em uma versão incompatível. |

`FeedDependencies` expõe `polling`, `state_db_path` e `runner`. Inicie processos externos
somente pelo `runner` (um `AsyncProcessRunner` que recebe um `CommandRequest`), nunca por um
shell. Guarde valores específicos da fonte em `Task.attributes`, um mapeamento de strings
persistido com a tarefa, para que o prompt continue sendo renderizado quando uma tarefa
interrompida for retomada.

O Curupira rejeita um plugin cujo `api_version` seja diferente de `PLUGIN_API_VERSION`, cujo
`trigger_type` já esteja registrado ou cujo `configuration_model` não use o tipo registrado
como padrão de `trigger_type`.

### Testando um plugin

Dá para testar o plugin sem instalá-lo: registre o trigger com
`curupira.tasks.registry.register`, valide uma configuração com
`ApplicationSettings.model_validate` e chame o trigger diretamente. A suíte do Curupira tem
um plugin de exemplo completo em `tests/plugins/ticket_plugin.py` e os testes
correspondentes em `tests/plugins/test_plugins.py`.

A referência gerada dos modelos fica na [página em inglês](../en/plugins.md#reference).
