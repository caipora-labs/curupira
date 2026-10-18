# GitHub Copilot CLI

O Curupira executa o `copilot` de forma não interativa, com saída JSONL, um ID de sessão persistido e
`--no-ask-user`. A CLI termina depois que o prompt é concluído. Atualmente o Curupira devolve o
JSONL capturado sem alterações, porque o schema de eventos das execuções programáticas de prompt não é
documentado; ele ainda não extrai uma mensagem final do assistente.

## Instalação

Instale `@github/copilot` com npm (`npm install -g @github/copilot`), use
`brew install copilot-cli` no Homebrew ou `winget install GitHub.Copilot` no Windows.

Veja o [guia oficial de instalação](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)
para os pré-requisitos e detalhes específicos de cada plataforma.

## Autenticação

Autentique-se com `copilot login` ou forneça um token suportado no ambiente. A precedência
dos tokens é `COPILOT_GITHUB_TOKEN`, depois `GH_TOKEN`, depois `GITHUB_TOKEN`. Personal access
tokens clássicos `ghp_` não são suportados pela Copilot CLI.

Se `GH_TOKEN` já estiver exportado para a GitHub CLI, o Copilot o usa antes de
`GITHUB_TOKEN`; garanta que esse token tenha acesso ao Copilot. O Curupira não gerencia nem repassa
credenciais de autenticação.

## Opções do profile

| Opção do profile | Argumento nativo |
| --- | --- |
| Mensagem da tarefa | `--prompt=<message>`; a forma com igual preserva um hífen no início do prompt |
| Sessão | `--session-id=<id>` para execuções novas e retomadas; o Curupira atribui o novo UUID |
| Saída | `--output-format=json`; o Curupira preserva o JSONL capturado sem alterações |
| Perguntas ao usuário | `--no-ask-user`, sempre habilitado pelo Curupira |
| `model` | `--model=<model>` (`auto` é aceito pela Copilot CLI) |
| `agent` | `--agent=<agent>` para um agente personalizado configurado |
| `effort` | `--reasoning-effort=<level>`: `low`, `medium`, `high`, `xhigh` ou `max` |
| `allow_all_tools` | `--allow-all-tools` |
| `allow_tools` | Um argumento `--allow-tool=<comma-separated-patterns>` |
| `deny_tools` | Um argumento `--deny-tool=<comma-separated-patterns>`; as regras de negação prevalecem sobre as de permissão |

O Curupira sempre passa `--no-ask-user`: o Copilot não pode parar para fazer uma pergunta enquanto uma tarefa
roda sem supervisão. Cada execução também passa `--output-format=json` e
`--session-id=<id>`. As execuções novas usam o UUID que o Curupira persistiu antes de iniciar a CLI;
as execuções retomadas passam o ID de sessão persistido com a mesma flag. Nenhuma flag `--resume`
separada é usada. O prompt da tarefa é passado como `--prompt=<message>` para que um hífen no início continue
fazendo parte do prompt.

### Permissões de ferramentas em modo headless

O uso de ferramentas em modo headless precisa de autorização explícita. Defina `allow_all_tools = true` para permitir
todas as ferramentas suportadas pela Copilot CLI, ou defina `allow_tools` para permitir explicitamente
ferramentas e padrões selecionados, como `shell(git:*)` e `write`. `deny_tools` pode negar
ferramentas explicitamente; as negações têm precedência sobre as permissões. As entradas de ferramentas não podem conter vírgulas, porque
o Curupira passa cada lista como um único argumento da CLI separado por vírgulas.

O Curupira nunca adiciona flags mais amplas, como `--allow-all`, `--yolo`, ou bypasses de caminho/URL.

## Referência de configuração { #configuration-reference }

::: curupira.agents.copilot.CopilotCliProfile
    options:
      inherited_members:
        - model
      members:
        - model

### Campo `model` herdado

O profile comum da CLI fornece `model`; o Copilot o mapeia para `--model=<model>`.
