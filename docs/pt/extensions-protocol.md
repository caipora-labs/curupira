# Manifesto e protocolo

Os SDKs implementam tudo o que está nesta página para você. Leia-a quando escrever uma extensão
sem um SDK, depurar uma ou quiser saber exatamente o que o host faz. A especificação
normativa é o
[`PROTOCOL.md`](https://github.com/caipora-labs/curupira/blob/main/packages/curupira-core/PROTOCOL.md).

## Transporte { #transport }

Versão **2** do protocolo: JSON-RPC 2.0 por stdin e stdout, em **frames prefixados pelo tamanho**
(nunca JSON delimitado por quebra de linha). Cada frame é formado por oito dígitos hexadecimais com o tamanho em bytes
do corpo JSON em UTF-8, seguidos diretamente pelo corpo, sem separador e sem quebra de linha:

```text
0000002c{"jsonrpc":"2.0","id":1,"method":"describe"}
```

- O **stdout** transporta apenas frames do protocolo. O **stderr** é para logs.
- O tamanho máximo padrão de um frame é 16 MiB.
- O host envia `initialize` com `protocol_version`; a extensão responde com a
  mesma versão major. Outras versões são rejeitadas com um erro claro.

## Métodos { #methods }

| Método | Quando o host o chama |
| --- | --- |
| `initialize` | Primeiro, para combinar a versão do protocolo |
| `describe` | Para listar os triggers |
| `trigger/schema` | Para obter o JSON Schema e os campos de prompt de um trigger |
| `trigger/validate` | Durante o `curupira validate` e antes das consultas, com a tabela da automação |
| `trigger/poll` | Para obter o próximo item |
| `trigger/onStarted` | Antes de o agente de código começar, com os campos do item |
| `trigger/onFinished` | Depois de o agente de código terminar, com os campos do item |
| `shutdown` | Para deixar o processo sair de forma limpa |

`trigger/onStarted` e `trigger/onFinished` recebem
`{ "trigger_type": "<local>", "values": [ ... ] }`. Eles não recebem estado do host, como
o prompt renderizado ou o caminho do worktree.

## Resultados da consulta { #results }

`trigger/poll` sempre retorna um objeto com um membro `values` obrigatório:

| `values` | Significado |
| --- | --- |
| `null` | Nada foi encontrado. O host encerra a rodada atual para esta automação. |
| `[]` | Um item foi encontrado, e ele não tem campos. |
| `[{ "key": "issue_number", "value": "42" }, …]` | Os campos do item, como strings. |

Omitir `values` é um erro de protocolo, diferente de `null`. O protocolo não
exige `id`, `title`, `url` nem nenhuma outra chave, e o host não as interpreta.

## O que o host faz com um item { #polling }

1. Ele valida a automação com `trigger/validate`, com os padrões aplicados.
2. Ele chama `trigger/poll` repetidamente, até `[settings.polling].batch_size` vezes por
   rodada. Os argumentos de consulta não são passados para a função do trigger.
3. Ele gera um hash do JSON canônico dos pares, na ordem recebida, que vira a identidade
   da tarefa. Uma identidade concluída nunca roda de novo; os mesmos pares em outra ordem são uma
   tarefa diferente.
4. Ele preenche `${key}` no prompt com o valor de cada par, em uma única passada. O texto inserido
   não é examinado de novo, então um valor `${other}` permanece literal, e um placeholder sem
   chave correspondente fica inalterado.

O host adiciona `${repository}` (a identidade na forge a partir do remote Git) e
`${automation}` (o nome da automação). Uma chave de resultado com qualquer um desses nomes é um erro. Chaves
que não são identificadores também funcionam: `${issue-number}`, `${foo.bar}`, `${123}`.

## Códigos de erro { #errors }

| Código | Significado |
| --- | --- |
| `-32700` | Erro de parse |
| `-32600` | Requisição inválida |
| `-32601` | Método não encontrado |
| `-32602` | Parâmetros inválidos |
| `-32603` | Erro interno |
| `-32000` | Falha de transporte |
| `-32001` | Falha de protocolo ou de versão |
| `-32002` | Falha na execução de comando |
| `-32003` | Falha na validação da configuração |
| `-32004` | Tempo esgotado |

## Manifesto { #manifest }

O `curupira-extension.toml` (formato de manifesto `1`) descreve um pacote para que o Curupira possa listá-lo
e instalá-lo sem executá-lo. Uma extensão precisa declarar `kind = "trigger"` e pelo
menos uma entrada em `trigger_types`.

```toml
manifest_version = 1
name = "acme-curupira-ext"
version = "1.2.0"
protocol_version = 2
runtime = "node"
kind = "trigger"
trigger_types = ["github-issue"]

[launch]
type = "npx"
package = "@acme/curupira-ext"
version = "1.2.0"
```

O pacote deve imprimir esse manifesto quando iniciado com `--curupira-print-manifest`, para que
`curupira plugins list` possa descrevê-lo sem executar nenhum código de trigger.
