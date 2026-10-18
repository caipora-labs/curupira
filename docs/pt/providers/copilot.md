# GitHub Copilot CLI

O Curupira executa a [GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli)
de forma não interativa, com saída JSON e um id de sessão atribuído por ele:

```text
copilot --output-format=json --no-ask-user --session-id=<id> [options] --prompt=<prompt>
```

## Instale e faça login { #install }

```sh
npm install -g @github/copilot   # ou: brew install copilot-cli / winget install GitHub.Copilot
copilot login
```

Veja o [guia oficial de instalação](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli)
para os pré-requisitos.

Em vez de `copilot login`, você pode fornecer um token. O Copilot lê `COPILOT_GITHUB_TOKEN`,
depois `GH_TOKEN` e depois `GITHUB_TOKEN`; tokens clássicos `ghp_` não são suportados. Se `GH_TOKEN`
já estiver exportado para a GitHub CLI, o Copilot o usa primeiro, então garanta que esse token
tenha acesso ao Copilot. O Curupira nunca lê nem repassa credenciais.

## Opções do perfil { #options }

| Opção | Argumento nativo | Observações |
| --- | --- | --- |
| `model` | `--model=<model>` | `auto` deixa o Copilot escolher. |
| `agent` | `--agent=<agent>` | Um agente personalizado configurado. |
| `effort` | `--reasoning-effort=<level>` | `low`, `medium`, `high`, `xhigh` ou `max`. |
| `allow_all_tools = true` | `--allow-all-tools` | Permite todas as ferramentas. |
| `allow_tools` | `--allow-tool=<a,b>` | Permite ferramentas e padrões selecionados, como `shell(git:*)` e `write`. |
| `deny_tools` | `--deny-tool=<a,b>` | Nega ferramentas; regras de negação prevalecem sobre regras de permissão. |

O Curupira sempre adiciona `--no-ask-user`, porque uma execução sem supervisão não pode parar para fazer uma
pergunta, e passa o prompt como `--prompt=<prompt>` para que um hífen inicial continue sendo texto.

### Permissões de ferramentas em modo headless { #configuration-reference }

Execuções headless precisam de permissões explícitas de ferramentas. Defina `allow_all_tools = true`, ou liste o que é
permitido em `allow_tools` e o que é proibido em `deny_tools`. Cada lista é passada como um único
argumento separado por vírgulas, então uma entrada não pode conter vírgula. O Curupira nunca adiciona flags
mais amplas como `--allow-all`, `--yolo` ou bypasses de caminho e de URL.

## Exemplo { #example }

```toml
[agents.profiles.copilot]
provider = "copilot"
model = "auto"
effort = "high"
allow_tools = ["shell(git:*)", "write"]
deny_tools = ["shell(rm:*)"]
```

## Sessões { #sessions }

O Curupira cria um UUID antes da primeira execução e o passa com `--session-id`. A mesma
flag retoma uma tarefa interrompida; nenhuma flag `--resume` separada é usada.
