# pi

O Curupira executa o [pi](https://www.npmjs.com/package/@earendil-works/pi-coding-agent) no modo
JSON:

```text
pi --mode json [options] -- <prompt>
```

## Instale e faça login { #install }

O pi precisa do Node.js 22.19.0 ou mais recente.

```sh
npm install -g @earendil-works/pi-coding-agent
```

Faça login com o comando `/login` do pi, ou exporte a variável de chave de API do seu provider
de modelos. O Curupira nunca lê nem armazena credenciais.

## Opções do perfil { #options }

| Opção | Argumento nativo | Observações |
| --- | --- | --- |
| `model` | `--model <model>` | Um padrão exato ou aproximado; pode incluir `provider/id`. |
| `model_provider` | `--provider <provider>` | Exige `model`. Tem esse nome para não conflitar com o `provider` do Curupira. |
| `effort` | `--thinking <level>` | `off`, `minimal`, `low`, `medium`, `high`, `xhigh` ou `max`. |
| `tools` | `--tools a,b` | Lista de ferramentas que o pi pode usar. |
| `exclude_tools` | `--exclude-tools a,b` | Ferramentas a remover. |
| `approve = true` | `--approve` | Confia nos recursos do projeto nesta execução. |
| `approve = false` | `--no-approve` | Não confia neles nesta execução. |
| `agent` | — | Não suportado; rejeitado. |

Quando `approve` é omitido, vale a configuração de confiança de projeto do próprio pi. O pi não pergunta antes
de cada chamada de ferramenta, e o modo JSON dele não consegue mostrar o pedido de confiança; quando essa configuração é
`ask`, os recursos protegidos do projeto são ignorados, a menos que você defina `approve`.

!!! note "Prompts que começam com `@`"
    O pi lê `@path` como inclusão de arquivo, então um prompt que começa com `@` pode ser tratado
    como referência a um arquivo.

## Exemplo { #example }

```toml
[agents.profiles.pi]
provider = "pi"
model = "anthropic/claude-sonnet-4"
model_provider = "anthropic"
effort = "high"
tools = ["read", "edit", "write"]
exclude_tools = ["bash"]
# approve = true   # confia nos recursos do projeto nesta execução
```

## Sessões { #sessions }

O pi escreve um cabeçalho de sessão na saída JSON; esse id é salvo com a tarefa. Uma
tarefa interrompida é retomada com `--session <id>` no mesmo worktree, porque o pi agrupa
as sessões por diretório.
