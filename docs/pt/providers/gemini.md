# Gemini CLI

O Curupira executa a Gemini CLI no modo não interativo `stream-json` e retoma sessões
com a opção nativa `--resume <session_id>` do Gemini.

## Instalação

A Gemini CLI exige Node.js 20 ou superior. Instale-a globalmente com npm:

```bash
npm install -g @google/gemini-cli
```

## Autenticação

A autenticação é responsabilidade da Gemini CLI. Entre pelo fluxo de conta Google, defina
`GEMINI_API_KEY` ou configure o ambiente para o Vertex AI. O Curupira não lê,
armazena nem gerencia credenciais de providers.

## Opções do Curupira

O Curupira mapeia os campos do profile Gemini para estes argumentos nativos:

| Opção | Argumento nativo |
| --- | --- |
| `model` | `--model <model>` opcional |
| `approval_mode` | `--approval-mode <mode>` opcional: `default`, `auto_edit`, `yolo` ou `plan` |
| `skip_trust` | `--skip-trust` quando `true` |
| `agent` | Não suportado; rejeitado |
| `effort` | Não suportado; rejeitado |

Quando `approval_mode` não está definido, as execuções headless usam a política de aprovação nativa da Gemini CLI.
Defini-lo seleciona um dos modos de aprovação explícitos do Gemini. **Aviso:** definir
`approval_mode = "yolo"` desativa os prompts de aprovação; use somente quando esse comportamento for
intencional. O Curupira usa o valor `--approval-mode yolo` em vez da flag
`--yolo`, que está obsoleta.

O prompt é passado como `--prompt=<message>`, mantendo como texto do prompt as mensagens que começam com `-`.
O identificador de sessão nativo do Gemini é capturado do evento `init`.

## Referência do profile

{% if page.url == "providers/gemini/" %}
::: curupira.agents.gemini.GeminiCliProfile
{% endif %}
