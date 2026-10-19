# OpenCode

O Curupira executa o [OpenCode](https://opencode.ai) no modo `run` com saída JSON. O diretório
de trabalho do processo é a worktree da tarefa.

OpenCode 1.x:

```text
opencode run --format json --dir <worktree> [options] -- <prompt>
```

Execuções headless do OpenCode 2.x usam um servidor privado (`--standalone`) para que a tarefa
mantenha o diretório da worktree e o próprio banco de dados. Sessões interativas da 2.x não
passam `--standalone`.

```text
opencode run --standalone --format json [options] -- <prompt>
```

## Instale e faça login { #install }

OpenCode 1.x (`opencode-ai`):

```sh
npm install -g opencode-ai
opencode auth login
```

OpenCode 2.x (`@opencode/cli`):

```sh
npm install -g @opencode/cli
opencode auth login
```

O OpenCode cuida da autenticação de cada provider de modelos. O Curupira nunca lê nem armazena
credenciais.

Com `api = "auto"` (o padrão), o Curupira executa `opencode --version` uma vez por binário
resolvido e escolhe o conjunto de flags a partir do primeiro `x.y.z` que encontrar (`1.19.3` é
1.x, `opencode v2.0.32` é 2.x). Defina `api` quando essa sondagem não conseguir ver uma versão.

## Opções do perfil { #options }

| Opção | Argumento nativo | Observações |
| --- | --- | --- |
| `api` | | `"v1"`, `"v2"` ou `"auto"` (padrão). Seleciona o conjunto de flags do OpenCode 1.x ou 2.x. |
| `model` | `--model <provider/model>` | Na 2.x, uma variante de raciocínio faz parte do modelo: `provider/model#variant`. |
| `agent` | `--agent <agent>` | Um agente personalizado do OpenCode. |
| `effort` | `--variant` na 1.x; `#variant` na 2.x | A 1.x headless passa `--variant`. A 2.x acrescenta `#<effort>` a `--model`. Ignorado quando `model` não está definido. Um modelo que já contém `#` não pode ser combinado com `effort`. |
| `auto_approve = true` | `--auto` | Aprova as permissões que não são negadas explicitamente. Use com cuidado. |

| Flag | OpenCode 1.x headless | OpenCode 2.x headless | OpenCode 2.x interativo |
| --- | --- | --- | --- |
| `--dir <worktree>` | passado | omitido; o diretório de trabalho do processo é a worktree | omitido |
| `--variant` | `effort` | omitido | omitido |
| `--model` | `model` | `model`, ou `model#effort` quando `effort` está definido | igual à 2.x headless |
| `--standalone` | omitido | sempre passado | omitido |
| `--session`, `--agent`, `--format json`, `--auto` | passados quando configurados | passados quando configurados | `--agent` e `--auto` quando configurados; sem `--format` |

Cada execução define `OPENCODE_DB` como `<worktree>.opencode.db` na 1.x e na 2.x, então tarefas
paralelas não compartilham sessões nem entradas de projeto do OpenCode. `--server` não é uma
opção de perfil.

## Exemplo { #example }

```toml
[agents.profiles.opencode]
provider = "opencode"
# api = "auto" # "v1", "v2" ou "auto" (padrão)
model = "anthropic/claude-sonnet-4"
agent = "build"
# effort = "high" # 1.x: --variant high; 2.x: --model anthropic/claude-sonnet-4#high
```

## Sessões { #sessions }

O id de sessão é o `sessionID` no topo de um evento JSON (1.x e 2.x). Ele é salvo com a tarefa.
Uma tarefa interrompida é retomada com `--session <session_id>`.
