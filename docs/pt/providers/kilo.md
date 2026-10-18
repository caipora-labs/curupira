# Kilo CLI

Instale o Kilo com npm:

```bash
npm install -g @kilocode/cli
```

Autentique-se com `kilo auth login` ou configure as credenciais de um provider de model suportado no Kilo. O Curupira não armazena, solicita nem gerencia credenciais; o Kilo e as
integrações com providers são responsáveis pela autenticação.

O Curupira invoca `kilo run --format json` e envia a mensagem da tarefa depois de `--`. Os eventos
JSONL do Kilo incluem um ID de sessão em cada registro, e as partes de texto usam o mesmo formato
`text`/`part.text` do OpenCode. Por isso o Curupira usa o parser e o renderizador de sessão compartilhados, e retoma uma
sessão salva com `--session <session_id>`.

| Opção do profile | Argumento nativo | Observações |
| --- | --- | --- |
| `model` | `--model <provider/model>` | Use o identificador `provider/model` do Kilo. |
| `agent` | `--agent <agent>` | Nome de um agente existente do Kilo. |
| `effort` | `--variant <effort>` | Variante de raciocínio específica do provider, como `high`, `max` ou `minimal`. |
| `auto_approve` | `--auto` quando `true` | Perigoso: aprova automaticamente as permissões que não foram negadas explicitamente. |
| ID da sessão | `--session <session_id>` | Adicionado pelo Curupira ao retomar uma tarefa. |
| Mensagem da tarefa | `-- <message>` | O separador evita que mensagens que começam com `-` sejam interpretadas como flags. |

`effort` é mapeado para `--variant`; o `--thinking` do Kilo apenas exibe os blocos de raciocínio e não é
usado como opção de esforço de raciocínio. Sem `auto_approve`, o Kilo rejeita os pedidos de permissão
durante execuções headless em vez de esperar por entrada interativa. Deixe
`auto_approve` desativado, a menos que esse comportamento de permissão mais amplo seja intencional.

::: curupira.agents.kilo.KiloCliProfile
