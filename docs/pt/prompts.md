---
render_macros: false
---

# Escrevendo prompts

O `prompt` de uma automação é o texto que o seu agente de código recebe. Você o escreve no
`settings.toml`; o Curupira preenche os detalhes de cada tarefa antes de o agente começar.

Comece simples e adicione lógica somente quando precisar.

## 1. Insira campos com `${name}`

```toml
prompt = "Resolva a issue ${issue_number}: ${issue_title}\n\n${issue_body}"
```

Use uma string de várias linhas para prompts mais longos. No TOML, strings com `"""` processam escapes como
`\n`; strings com `'''` são tomadas literalmente:

```toml
prompt = """
Resolva a issue ${issue_number} em ${repo}.

${issue_body}
"""
```

Listas (como labels) são inseridas como JSON, por exemplo `["bug","security"]`.

## 2. Torne-o dinâmico

Para qualquer coisa além de inserir valores, use a sintaxe Jinja. Você pode misturá-la livremente com `${name}`.

| Você quer | Escreva |
| --- | --- |
| Um valor | `{{ issue_title }}` |
| Um valor reserva para um campo vazio ou opcional | `{{ issue_milestone \| default("none") }}` |
| Texto apenas em alguns casos | `{% if "security" in issue_labels \| fromjson %}...{% endif %}` |
| Duas alternativas | `{% if item_type == "pull_request" %}...{% else %}...{% endif %}` |
| Repetir para cada item de uma lista | `{% for label in issue_labels \| fromjson %}- {{ label }}\n{% endfor %}` |
| Encurtar um texto longo | `{{ issue_body \| truncate(2000) }}` |
| Comparar um número | `{% if pull_request_changed_files \| int > 20 %}...{% endif %}` |

Exemplo: uma automação que se adapta ao que recebe (mais exemplos em [Receitas](recipes.md)):

```toml
[automations.work-ready-column]
trigger_type = "plugins-py/github-project-items"
repository = "api"
owner = "acme"
project = 5
column = ["Ready"]
prompt = """
{% if item_type == "pull_request" %}
Revise o pull request #{{ item_number }} ({{ pull_request_head_ref }} -> {{ pull_request_base_ref }}).
Rascunho: {{ pull_request_is_draft }}.
{% else %}
Resolva a issue #{{ item_number }}: {{ item_title }}
{% endif %}

{% if "security" in item_labels | fromjson %}
Esta é uma issue de segurança. Mantenha a mudança mínima e explique o risco na mensagem de commit.
{% endif %}

${item_body}
"""
```

Observações:

- A quebra de linha após uma tag `{% ... %}` é mantida, então um bloco em uma linha própria deixa uma linha
  em branco. Use `{%- ... -%}` para remover o espaço em branco ao redor de uma tag quando isso importar.
- O Jinja tem muitos outros [filtros e testes embutidos](https://docs.rs/minijinja/latest/minijinja/filters/index.html)
  (`upper`, `join`, `length`, `first`, `selectattr`, ...).

## Todo valor é texto { #values-are-text }

O trigger entrega ao Curupira texto simples para cada campo, então algumas conversões são explícitas:

- **Listas e objetos** (labels, responsáveis, campos do projeto) chegam como texto JSON, por exemplo
  `["bug","security"]`. Use `| fromjson` para testá-los ou percorrê-los:
  `{% if "bug" in issue_labels | fromjson %}`.
- **Números** também são texto. Use `| int` para comparar: `{% if item_number | int > 100 %}`.
- **Booleanos** são `true` ou `false`: `{% if pull_request_is_draft == "true" %}`.
- **`${name}` e `{{ name }}` diferem quando falta um campo.** Um `${name}` que não corresponde a nenhum campo é
  deixado como escrito, então texto de shell como `${HOME}` é seguro. Um `{{ name }}` é um erro, o que
  pega erros de digitação. Use `{{ name | default("") }}` para campos que podem estar ausentes.
- **Chaves literais.** Para imprimir `{{` ou `{%` (por exemplo um `${{ secrets.X }}` do GitHub Actions),
  envolva o texto em `{% raw %}...{% endraw %}`.

## Campos

O host adiciona dois campos a toda tarefa: `${repository}` (o `owner/name` do GitHub do
repositório da automação) e `${automation}` (o nome da automação). Em um prompt de cron esses são
os únicos campos.

Cada trigger adiciona seus próprios campos. A lista completa está na [Referência de campos do prompt](prompt-fields.md),
e [Receitas](recipes.md) traz automações completas para copiar.

## Verificando o seu prompt

1. `curupira --config settings.toml validate` verifica a sintaxe e se todo `{{ field }}` que você usa
   existe. Um `${field}` só é verificado quando parece um erro de digitação de um campo real, porque
   outros nomes podem ser texto de shell. Um erro de digitação recebe uma sugestão:

   ```text
   automation "work-ready-column": prompt uses unknown field(s) "item_titel"
   (did you mean "item_title"?). Available fields: ...
   ```

2. `curupira --config settings.toml run --dry-run` encontra uma tarefa correspondente e imprime o prompt
   final, sem fazer clone nem iniciar um agente. Esta é a forma mais rápida de ver o que o
   agente vai receber.

Um `{{ field }}` que não tem valor para uma determinada tarefa (por exemplo, um campo de pull request em
uma issue), é um erro quando a tarefa roda, e não uma string vazia. Proteja-se com `default("")` ou
com um `{% if %}`.

## Segurança

Títulos e corpos vêm de outras pessoas. O texto deles é inserido como texto simples
e nunca é interpretado como template, então `{{ ... }}` dentro do corpo de uma issue não faz nada. Mesmo assim, ele pode
tentar direcionar o agente, então siga os conselhos das
[notas de segurança](github.md#security).
