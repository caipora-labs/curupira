# Extensões de processo

A CLI do Curupira é um binário Rust. As **fontes de tarefas** (exceto o **cron** embutido)
rodam como **processos separados** que falam o
[protocolo de extensões](https://github.com/caipora-labs/curupira/blob/main/packages/curupira-core/PROTOCOL.md)
(JSON-RPC 2.0 sobre stdin/stdout com prefixo de tamanho).

Os **agentes de código** (OpenCode, Claude Code, Codex, Cursor, Gemini CLI, GitHub Copilot CLI,
Kilo, pi, Qwen Code) são **embutidos no núcleo em Rust**. Eles não são extensões de processo
e não usam o protocolo de extensões.

## Instale a CLI { #install-the-cli }

```bash
pip install curupira
# or
uv tool install curupira
```

`curupira` e `curu` são o mesmo binário. O wheel base traz apenas essa CLI em Rust
(mais um shim fino `curupira.__version__`). Os triggers oficiais vêm em um único pacote
opcional (`curupira-plugins`, que depende de `curupira-sdk`): instale com extras ou com
`curupira plugins install`. O **cron** embutido não precisa de nenhum pacote de extensão. O
Node.js só é necessário quando você instala uma extensão de trigger de terceiros baseada em Node.

```bash
# triggers oficiais (instala o curupira-sdk como dependência)
pip install 'curupira[extensions]'
# os extras com nome de forge instalam o mesmo pacote
pip install 'curupira[github]'
# ou gerencie um pacote com a CLI (usa uvx)
curupira plugins install --yes pip:curupira-plugins
```

## Gerencie extensões { #manage-extensions }

```bash
curupira plugins list
curupira plugins info curupira-plugins
curupira plugins install --yes path:./packages/curupira-python-plugins
curupira plugins install --yes pip:some-extension==1.2.3
curupira plugins install --yes npm:@acme/curupira-ext@1.2.3
curupira plugins uninstall some-extension
```

A descoberta lê os manifestos `curupira-extension.toml` de
`~/.curupira/extensions/`, de `CURUPIRA_EXTENSIONS_PATH` e do `packages/curupira-python-plugins/` incluído.
**Listar nunca executa código de extensão.**

`plugins list` também mostra o cron embutido e os providers de agentes de código embutidos
(rotulados como `agent:<name>` com origem `built-in`).

### Requisitos de execução { #runtime-requirements }

| Origem | Necessário no PATH |
| --- | --- |
| Extras oficiais de triggers em Python / instalações gerenciadas | `python3` (ou `uvx` para instalações `pip:`) |
| Instalações `pip:` | `uvx` (do [uv](https://docs.astral.sh/uv/)) |
| Instalações `npm:` | `npx` (Node.js) |
| Cron embutido e agentes de código | as CLIs de agente que você configurar (mais `git`) |

## Extensões oficiais { #official-extensions }

Empacotadas como um único pacote do PyPI, `curupira-plugins`
(`packages/curupira-python-plugins/`, import `curupira_plugins`). Ele **não** é necessário
para instalar a CLI. Os extras do PyPI `github` / `extensions`
instalam essa mesma distribuição. Registre-o nas configurações sob um alias TOML com um
launcher independente (`uvx` ou `npx`) e args; as automações então usam
`<alias>/<local-trigger>`:

```toml
[plugins.plugins-py]
type = "uvx"
args = ["--from", "curupira-plugins", "curupira-plugins"]
tools = ["*"]
```

O pacote traz um script de console `curupira-plugins`, então o `uvx` o executa diretamente
(sem `python -m`). Use `tools` para manter apenas os triggers locais que correspondem
(`github-*`) ou para descartar correspondências (`!github-project-*`).

| Trigger local (no pacote) | `trigger_type` de automação de exemplo |
| --- | --- |
| `github-issues` | `plugins-py/github-issues` |
| `github-pull-requests` | `plugins-py/github-pull-requests` |
| `github-project-items` | `plugins-py/github-project-items` |

O **cron** e todos os adaptadores de agentes de código continuam dentro da CLI em Rust (não
são extensões).

## Escreva uma extensão em Python com curupira-sdk { #write-a-python-extension-with-curupira-sdk }

Instale o SDK separadamente (apenas biblioteca padrão por padrão; o Pydantic é opcional). Os
pacotes oficiais de triggers dependem dele; pacotes de terceiros devem declará-lo
explicitamente:

```bash
pip install curupira-sdk
# modelos estruturados opcionais:
pip install 'curupira-sdk[pydantic]'
```

### Trigger mínimo { #minimal-trigger }

```python
from dataclasses import dataclass

from curupira_sdk import Curupira

app = Curupira(name="acme-issues", version="0.1.0")


@dataclass
class Issue:
    number: int
    title: str
    url: str
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(self.number)


@app.trigger
async def github_issues(
    repo: str,
    labels: list[str] | None = None,
    state: str = "open",
) -> Issue | None:
    """Return the next eligible issue, or None when the round is empty."""
    # Selecione exatamente o próximo item da API externa (nunca uma lista).
    return None


def main() -> None:
    app.run()


if __name__ == "__main__":
    main()
```

Regras:

- Use `@app.trigger` sem parênteses para derivar o nome **local** do trigger a partir de
  `function.__name__` em kebab-case (`github_issues` → `github-issues`).
- Use `@app.trigger(alias="issues")` para sobrescrever o nome local.
- Registre o launcher em `[plugins.<alias>]` nas configurações (`type` + `args`).
  As automações endereçam o trigger como `<alias>/<local-name>` (por exemplo,
  `plugins-py/github-issues`).
- Os parâmetros da função são a fonte da verdade para os extras do TOML. Obrigatório /
  opcional / valores padrão / `None` vêm da assinatura e das type hints.
- Retorne **um** objeto ou `None`. Listas, tuplas e iteradores são rejeitados.
- `def` síncrono e `async def` usam o mesmo decorator.
- Dataclasses e TypedDict funcionam sem configuração. Modelos Pydantic v2 exigem
  `curupira-sdk[pydantic]`.
- O host em Rust cuida de polling, concorrência, Git, worktrees e agentes de código.
  O SDK nunca agenda nem repete o trabalho do dispatcher.

### TOML correspondente { #matching-toml }

Registre o launcher em `[plugins.<alias>]` e depois mantenha os campos centrais da
automação na tabela, com os argumentos do trigger como campos irmãos:

```toml
[plugins.plugins-py]
type = "uvx"
args = ["--from", "curupira-plugins", "curupira-plugins"]
tools = ["github-*"]

[automations.resolve-ready-issues]
trigger_type = "plugins-py/github-issues"
repository = "api"          # alias do checkout (núcleo)
repo = "acme/api"           # parâmetro da função
labels = ["bug"]
state = "open"
prompt = """
Resolve issue ${number}: ${title}
${url}
"""
```

`repository`, `prompt`, `profile` e `checkout` são campos centrais — não os declare
como parâmetros da função (use `repo` ou outro nome para identificadores de forge).

### Como o host consulta { #how-the-host-polls }

1. O host escolhe uma automação habilitada e valida a configuração via
   `trigger/validate` (com os padrões aplicados a partir da assinatura).
2. Ele chama `trigger/poll` repetidamente, até `settings.polling.batch_size`.
3. Cada chamada deve retornar `{ "task": <object> }` ou `{ "task": null }`.
4. `null` encerra a rodada atual; o trigger continua habilitado para o próximo intervalo de
   polling. Erros usam códigos de erro do JSON-RPC e não são o mesmo que `null`.

### Manifesto { #manifest }

Inclua um `curupira-extension.toml` e suporte `--curupira-print-manifest` no
stdout para `plugins install pip:…`. Veja `packages/curupira-core/tests/fixtures/python-ext/`
para um fixture mínimo do protocolo e
`packages/curupira-python-plugins/src/curupira_plugins/__main__.py` para um exemplo completo com o SDK.

As extensões descobrem e normalizam tarefas, validam sua configuração e recebem
eventos de ciclo de vida. Elas não devem escolher agentes de código, montar o argv do agente, clonar
repositórios nem gerenciar worktrees — o host em Rust cuida dessas etapas.

## Escreva uma extensão em JavaScript / TypeScript { #write-a-javascript-typescript-extension }

Use o mesmo enquadramento e os mesmos métodos. Publique um pacote npm cujo `bin` fale o
protocolo via stdio. Pacotes em TypeScript devem ser compilados para JS ou rodar com
`tsx`/`node`, conforme documentado no pacote. Veja
`packages/curupira-core/tests/fixtures/node-ext/` e
`packages/curupira-core/tests/fixtures/ts-ext/`.

Os resultados do poll devem usar `{ "task": null }` ou um único objeto de tarefa — nunca um
array de tarefas.

## Segurança { #security }

Extensões de terceiros rodam com os privilégios do seu usuário. Subprocessos não são um
sandbox. Não instale pacotes não confiáveis. O Curupira nunca instala pacotes
durante a descoberta; os comandos de instalação pedem confirmação, a menos que `--yes` seja usado.
