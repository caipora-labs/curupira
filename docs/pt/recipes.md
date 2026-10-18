---
render_macros: false
---

# Receitas

Copie uma, altere os nomes dos repositórios e execute `curupira validate` seguido de
`curupira run --dry-run`. Toda receita pressupõe as configurações do
[início rápido](index.md#quick-start) (um alias de repositório, um perfil de agente e
o registro `[plugins.plugins-py]`).

## Resolver issues que têm uma label

```toml
[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
exclude_labels = ["blocked"]
linked_pull_request = false          # ignora issues que já têm um pull request
prompt = """
Resolva a issue #${issue_number}: ${issue_title}

${issue_body}

Abra um pull request quando terminar.
"""
```

## Revisar pull requests que estão prontos

Apenas pull requests que não são rascunhos, não têm conflitos e têm checks passando.

```toml
[automations.review-pull-requests]
trigger_type = "plugins-py/github-pull-requests"
repository = "api"
repo = "acme/api"
draft = false
mergeable = true
ci_status = "success"
labels = ["review-needed"]
prompt = """
Revise o pull request #${pull_request_number}: ${pull_request_title}
Branch: ${pull_request_head_ref} -> ${pull_request_base_ref}
Arquivos alterados: ${pull_request_changed_files} (+${pull_request_additions} -${pull_request_deletions})

${pull_request_body}
"""
```

## Fazer merge de atualizações do Dependabot

```toml
[automations.merge-dependabot]
trigger_type = "plugins-py/github-pull-requests"
repository = "api"
repo = "acme/api"
author = "app/dependabot"
draft = false
mergeable = true
prompt = """
Analise o pull request #${pull_request_number} do Dependabot (${pull_request_title}) em ${repo}.
Corrija o que a atualização quebrar, aguarde os checks e então faça squash merge com
`gh pr merge ${pull_request_number} --repo ${repo} --squash`.
"""
```

O perfil do agente precisa de `auto_approve = true` para que escritas do `gh` sem supervisão não parem
esperando aprovação. Veja [Providers e agentes](providers.md).

## Tratar o feedback de revisão

Pegue pull requests em que um revisor pediu mudanças. A conversa de revisão não é um campo do prompt
(veja [Deixado de fora de propósito](prompt-fields.md#left-out-on-purpose)), então o prompt diz ao
agente onde lê-la.

```toml
[automations.address-feedback]
trigger_type = "plugins-py/github-pull-requests"
repository = "api"
repo = "acme/api"
review = "changes_requested"
draft = false
prompt = """
O pull request #${pull_request_number} precisa de mudanças: ${pull_request_title}

Leia a revisão com `gh pr view ${pull_request_number} --repo ${repo} --comments` e
`gh api repos/${repo}/pulls/${pull_request_number}/comments`, depois faça as mudanças solicitadas na
branch ${pull_request_head_ref}.
"""
```

## Trabalhar a partir de uma coluna do board

Uma automação trata tanto issues quanto pull requests que estão na coluna `Ready`.

```toml
[automations.board-ready]
trigger_type = "plugins-py/github-project-items"
repository = "api"
owner = "acme"
project = 5
column = "Ready"
repo = "acme/api"
prompt = """
{% if item_type == "pull_request" %}
Revise o pull request #{{ item_number }} ({{ pull_request_head_ref }} -> {{ pull_request_base_ref }}).
{% else %}
Resolva a issue #{{ item_number }}: {{ item_title }}
{% endif %}

${item_body}
"""
```

## Adaptar o prompt às labels

```toml
[automations.triage]
trigger_type = "plugins-py/github-issues"
repository = "api"
repo = "acme/api"
labels = ["agent-ready"]
prompt = """
Resolva a issue #${issue_number}: ${issue_title}

{% if "security" in issue_labels | fromjson %}
Esta issue está relacionada à segurança. Mantenha a mudança mínima e descreva o risco na mensagem de commit.
{% elif "bug" in issue_labels | fromjson %}
Isto é um bug. Escreva primeiro um teste que falhe e depois corrija.
{% else %}
Implemente o pedido e adicione testes.
{% endif %}

${issue_body}
"""
```

## Usar a prioridade do card de um board

```toml
[automations.prioritized]
trigger_type = "plugins-py/github-project-items"
repository = "api"
owner = "acme"
project = 5
column = ["Ready"]
prompt = """
{% set card = project_fields | fromjson %}
Prioridade: {{ card.Priority | default("not set") }}

Resolva #${item_number}: ${item_title}

${item_body}
"""
```

## Uma tarefa de manutenção semanal (sem GitHub)

```toml
[automations.weekly-maintenance]
trigger_type = "cron"
repository = "api"
schedule = "0 9 * * 1"        # toda segunda-feira às 09:00 no fuso horário configurado
prompt = """
Verifique as dependências e a configuração de CI de ${repository}. Abra um pull request com
as atualizações seguras. Automação: ${automation}.
"""
```
