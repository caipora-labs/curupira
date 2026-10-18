---
render_macros: false
---

# GitHub Projects (colunas do board)

`plugins-py/github-project-items` transforma uma coluna de um board do GitHub Projects em uma fila de trabalho.
Mova um card para a coluna que você escolheu, e o Curupira entrega essa issue ou esse pull request ao seu
agente de código. Funciona com projetos de usuário e de organização (o novo "Projects", também chamado
de Projects v2).

```toml
[automations.work-ready-column]
trigger_type = "plugins-py/github-project-items"
repository = "api"          # alias do checkout onde o agente roda
owner = "acme"              # usuário ou organização dona do projeto
project = 5                 # o número na URL do projeto
column = "Ready"            # um valor do campo Status
prompt = """
{% if item_type == "pull_request" %}Revise{% else %}Resolva{% endif %} #${item_number}: ${item_title}

${item_body}
"""
```

## Antes de começar

1. Faça login com a GitHub CLI e adicione o escopo de projetos. Sem `read:project`, o GitHub
   informa que o projeto não existe.

   ```sh
   gh auth login
   gh auth refresh -s read:project
   ```

2. Descubra o **número do projeto**. Ele é o número no final da URL do projeto:
   `https://github.com/orgs/acme/projects/5` é o projeto `5` do owner `acme`. Você também pode listar
   os projetos:

   ```sh
   gh project list --owner acme        # a primeira coluna é o número
   gh project list --owner @me         # seus projetos pessoais
   ```

3. Descubra os **nomes exatos das colunas**. Eles são as opções do campo `Status`:

   ```sh
   gh project field-list 5 --owner acme
   ```

## Campos

| Campo | Padrão | Significado |
| --- | --- | --- |
| `owner` | *(obrigatório)* | Login do usuário ou da organização dona do projeto |
| `project` | *(obrigatório)* | Número do projeto |
| `column` | *(obrigatório)* | Um nome de coluna ou uma lista. Não diferencia maiúsculas de minúsculas |
| `status_field` | `"Status"` | O campo de seleção única que guarda a coluna. Altere se o seu board usa outro campo, por exemplo `"Stage"` |
| `content` | `"all"` | `"issue"`, `"pull_request"` ou `"all"` |
| `repo` | nenhum | Apenas itens deste `owner/name`. Projetos costumam abranger vários repositórios |
| `state` | `"open"` | `"open"`, `"closed"` ou `"all"` |
| `labels` | nenhum | Todas as labels listadas devem estar no item |
| `exclude_labels` | nenhum | Nenhuma das labels listadas pode estar no item |
| `assignee` | nenhum | Um login, `"none"` (sem responsável) ou `"any"` (atribuído a alguém) |
| `author` | nenhum | O login do autor |

Cards de rascunho (notas que ainda não são issues) e cards arquivados são sempre ignorados, porque
não têm um repositório onde trabalhar.

!!! note "Itens fechados"
    `state` tem como padrão `"open"`, então uma issue fechada que ainda está em uma coluna é
    ignorada. Use `state = "all"` se você quiser que a coluna seja a única regra.

## Em qual repositório o agente trabalha?

Um board pode conter itens de vários repositórios, mas cada automação roda em um único checkout,
o alias `repository`. Duas configurações comuns:

- **Um repositório por board.** Defina `repo = "acme/api"` e `repository = "api"`.
- **Vários repositórios.** Crie uma automação por repositório, cada uma com seu próprio `repo`
  e `repository`, todas apontando para o mesmo projeto e a mesma coluna.

No prompt, `${repo}` é sempre o repositório do item encontrado, o que é útil para
comandos `gh`.

## Um fluxo de trabalho guiado por colunas

Use uma coluna por etapa e uma automação por etapa. Os agentes passam de uma para a próxima quando
você (ou uma automação posterior) move o card:

| Coluna | Automação | O que o agente faz |
| --- | --- | --- |
| `Ready` | `column = "Ready"` | Implementa a issue e abre um pull request |
| `Review` | `column = "Review"`, `content = "pull_request"` | Revisa o pull request e comenta |

Uma tarefa é identificada pelos valores exatos do card. Quando o agente termina com sucesso, esses
valores são lembrados, então a mesma issue ou o mesmo pull request na mesma coluna, com o mesmo título,
labels e campos, não é executado novamente pela mesma automação, mesmo após uma reinicialização ou se você arrastar
o card para fora e de volta. Editar o item (ou movê-lo para outra coluna) o torna uma nova
tarefa. Veja [Deduplicação](github.md#deduplication). Cards cuja execução do agente falhou são tentados novamente
após uma reinicialização.

## O que o prompt pode usar

Os itens de projeto expõem os campos `${item_*}`, `${project_*}` e alguns `${pull_request_*}`. Veja
a [Referência de campos do prompt](prompt-fields.md#project-items). A
coluna em que o item foi encontrado é `${project_column}`, e cada campo do card (por exemplo
`Priority` ou `Iteration`) está em `${project_fields}` como JSON:

```toml
prompt = """
{% set fields = project_fields | fromjson %}
Prioridade: {{ fields.Priority | default("none") }}
"""
```

## Solução de problemas

| Mensagem ou sintoma | Causa e correção |
| --- | --- |
| `GitHub project 5 not found for 'acme'` | Owner ou número errado, ou o token não tem `read:project`. Execute `gh auth refresh -s read:project` e confira a URL |
| Nada é encontrado, mas a coluna tem cards | Os cards estão fechados (`state = "all"`), são rascunhos, pertencem a outro `repo`, ou o nome da coluna é diferente. Compare com `gh project field-list` |
| Um `status_field` personalizado não encontra nada | Use o nome exato do campo, por exemplo `status_field = "Stage"` |
| `column: Value error` vindo do `validate` | `column` está vazio. Informe pelo menos um nome |
