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
# Node.js
npm install -g @caipora/curupira

# Python
pip install curupira
# or
uv tool install curupira
```

`curupira` e `curu` executam o mesmo binário Rust nos dois casos, e ambos usam
`~/.curupira/`. O pacote npm não altera os launchers de extensões e não instala um
ambiente Python ou Node.js próprio. O wheel do PyPI também traz um shim fino
`curupira.__version__`. Os triggers oficiais vêm em um único pacote opcional
(`curupira-plugins`, que depende de `curupira-sdk`): instale com extras ou com
`curupira plugins install`. O **cron** embutido não precisa de nenhum pacote de extensão. As
extensões `uvx` precisam de `uvx` no `PATH`; as extensões `npx` precisam de `npx` no `PATH`. Se o
launcher configurado não existir, a validação informa isso.

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


@app.trigger
async def github_issues(
    repo: str,
    labels: list[str] | None = None,
    state: str = "open",
) -> Issue | None:
    """Return the next issue, or None when nothing was found."""
    # Selecione exatamente um objeto (nunca uma lista). None significa que nada foi encontrado.
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
- Retorne **um** objeto ou `None`. `None` significa que nada foi encontrado e vira
  `null` em JSON. Listas, tuplas, sets e iteradores são rejeitados, inclusive uma
  lista de pares montada manualmente. Um mapeamento vazio vira uma lista de pares
  vazia, que é um item sem dados, não "nada encontrado".
- `def` síncrono e `async def` usam o mesmo decorator. O host não passa
  `preview` nem `limit` para a função.
- Mapeamentos, dataclasses e TypedDicts funcionam sem configuração. Modelos Pydantic v2
  exigem `curupira-sdk[pydantic]`. O SDK converte esse objeto em uma lista de pares de
  strings `{ "key", "value" }`. Ele não adiciona `id`, `title`, `url` nem
  qualquer outro campo.
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
Os nomes no prompt são os campos que o trigger retorna. Este exemplo
usa apenas `number`, `title` e `url` porque `Issue` declara esses campos.

### Como um valor de retorno vira pares { #how-a-return-value-becomes-pairs }

O SDK converte o objeto antes que ele chegue ao host. As chaves de nível superior mantêm a
ordem de declaração ou de inserção. Cada valor vira uma string:

| Valor em Python | `value` do par |
| --- | --- |
| `str` | a mesma string, sem aspas extras |
| `bool` | `true` ou `false` |
| `int` | texto decimal (`1` e `1.0` continuam distintos) |
| `float` | o mesmo texto que `json.dumps` emitiria |
| `None` | `null` (isto é um valor de campo, não "nada encontrado") |
| mapeamento aninhado, lista, tupla, dataclass ou modelo | JSON compacto (`sort_keys=True`, sem espaços extras) |

Rejeitados com `SerializationError` (exibido como erro JSON-RPC, não como `null`):

- uma lista, tupla, set, gerador ou outra coleção no nível superior
- uma string, número ou booleano no nível superior
- uma chave que não é string (as chaves não são convertidas com `str`)
- uma chave vazia, ou uma chave contendo `}` ou `${`
- uma chave duplicada
- um float não finito, `bytes`, `set`, `datetime` ou qualquer outro valor que não possa ser serializado

O `describe` ainda pode listar `prompt_fields` tirados do tipo de retorno declarado.
Essa lista é uma dica. Ela não faz parte do resultado e não torna nenhuma chave
obrigatória.

### Como o host consulta e interpola { #how-the-host-polls-and-interpolates }

1. O host escolhe uma automação habilitada e valida a configuração via
   `trigger/validate` (com os padrões aplicados a partir da assinatura).
2. Ele chama `trigger/poll` repetidamente, até `settings.polling.batch_size`.
   Os argumentos de polling não são passados para a função do trigger.
3. Cada chamada retorna `{ "values": [ {"key", "value"}, ... ] }`,
   `{ "values": [] }` ou `{ "values": null }`.
4. `null` encerra a rodada atual. Uma lista vazia ainda é um resultado. Erros usam
   códigos de erro do JSON-RPC e não são o mesmo que `null`.

A CLI substitui `${key}` pelo valor string do par em uma única passagem. O texto
que um valor insere não é examinado de novo, então um valor `${other}` permanece
literal. Um placeholder sem chave correspondente é deixado como está. `${repository}`
(a identidade da forge derivada do remote do Git) e `${automation}` (o nome da
automação) são fornecidos pelo host. Uma chave de resultado com qualquer um desses
nomes é um erro. Chaves que não são identificadores comuns continuam sendo escritas como
`${issue-number}`, `${foo.bar}`, `${123}` ou `${a b}`.

O host não sabe quais chaves um plugin usa. Duas listas idênticas são a
mesma tarefa; a identidade é um hash da lista na ordem em que a extensão a enviou,
armazenado junto com o estado de conclusão e de retomada. Tarefas concluídas do protocolo v1
não correspondem a essas chaves.

### Manifesto { #manifest }

Inclua um `curupira-extension.toml` e suporte `--curupira-print-manifest` no
stdout para `plugins install pip:…`. Veja `packages/curupira-core/tests/fixtures/python-ext/`
para um fixture mínimo do protocolo e
`packages/curupira-python-plugins/src/curupira_plugins/__main__.py` para um exemplo completo com o SDK.

As extensões descobrem e normalizam tarefas, validam sua configuração e recebem
eventos de ciclo de vida. Elas não devem escolher agentes de código, montar o argv do agente, clonar
repositórios nem gerenciar worktrees — o host em Rust cuida dessas etapas.

## Escreva uma extensão em JavaScript / TypeScript com `@caipora/curupira-sdk` { #javascript-extension }

Instale o SDK no seu pacote npm (Node.js 20+). A CLI inicia o pacote publicado
com `npx`; você não precisa de uma instalação global do plugin nem do SDK.

```bash
npm install @caipora/curupira-sdk
```

### Trigger mínimo em JavaScript (JSDoc opcional) { #minimal-javascript-trigger-jsdoc-optional }

```js
import { defineTriggers } from "@caipora/curupira-sdk";

/**
 * @typedef {Object} GitHubIssueParams
 * @property {string} repo
 * @property {string[]} [labels]
 */

/**
 * @param {GitHubIssueParams} params
 */
async function githubIssue({ repo, labels = [] }) {
  // Retorne um objeto, ou null quando nada foi encontrado.
  return { repo, labels, title: "Fix authentication" };
}

export default defineTriggers({
  githubIssue,
});
```

O JSDoc é documentação para editores. Ele não é lido em tempo de execução.

### Trigger mínimo em TypeScript { #minimal-typescript-trigger }

```ts
import { defineTriggers } from "@caipora/curupira-sdk";

export default defineTriggers({
  githubIssue: async (params: { repo: string; labels?: string[] }) => ({
    repo: params.repo,
    labels: params.labels ?? [],
    title: "Fix authentication",
  }),
});
```

Compile o TypeScript para ESM JavaScript puro antes de publicar. O Curupira não
transpila TypeScript arbitrário quando inicia o plugin.

### Entrypoint `bin` do plugin { #plugin-bin-entrypoint }

```js
#!/usr/bin/env node
import { runExtension } from "@caipora/curupira-sdk";
import triggers from "./index.js";

await runExtension(triggers, {
  name: "@acme/curupira-ext",
  version: "1.2.0",
  // Opcional: exibido por `curupira plugins install npm:…`
  manifestTemplate: `manifest_version = 1
name = "acme-curupira-ext"
version = "{version}"
protocol_version = 2
runtime = "node"
kind = "trigger"
trigger_types = ["github-issue"]

[launch]
type = "npx"
package = "@acme/curupira-ext"
version = "{version}"
`,
});
```

Declare o executável no `package.json`:

```json
{
  "name": "@acme/curupira-ext",
  "version": "1.2.0",
  "type": "module",
  "bin": {
    "curupira-acme-ext": "./bin.js"
  },
  "dependencies": {
    "@caipora/curupira-sdk": "^0.1.0"
  }
}
```

Publique no npm. Registre o launcher nas configurações (fixe a versão em `args`):

```toml
[plugins.acme]
type = "npx"
args = ["--yes", "@acme/curupira-ext@1.2.0"]
tools = ["*"]

[automations.demo]
trigger_type = "acme/github-issue"
repository = "api"
repo = "acme/api"
labels = ["bug"]
prompt = """
Resolve ${title} in ${repo}
"""
```

A CLI executa `npx --yes @acme/curupira-ext@1.2.0` como argv (nunca como string de shell),
encaminha stdin/stdout para os frames do protocolo e deixa o stderr para logs. O cache
normal do npm é usado. Se o `npx` não existir, o validate falha com uma mensagem que
indica a instalação do Node.js.

### Regras do SDK de JS/TS { #rules-for-the-jsts-sdk }

- O nome da propriedade do objeto é o id local do trigger, convertido para kebab-case
  (`githubIssue` → `github-issue`).
- Funções síncronas e assíncronas são suportadas.
- Retorne **um** objeto simples ou `null`. O SDK converte o objeto em pares de strings
  `{ "values": [{ "key", "value" }, ...] }`. `null` vira
  `{ "values": null }`. Um objeto vazio vira `{ "values": [] }`.
- Não monte a lista de pares manualmente. Não retorne um array de itens de negócio.
- Valores aninhados usam as mesmas regras de serialização do SDK de Python (veja acima).
- Os campos centrais da automação (`trigger_type`, `repository`, `prompt`, `profile`,
  `checkout`) não são parâmetros da função — use `repo` (ou similar) para identificadores de forge.
- As flags de polling (`preview`, `limit`) não são passadas para a função do trigger.
- O pacote é ESM. Prefira publicar JavaScript compilado junto com arquivos `.d.ts`.

Os fixtures de protocolo de baixo nível, sem o SDK, continuam em
`packages/curupira-core/tests/fixtures/node-ext/` e `ts-ext/`. Exemplos completos
estão em `packages/curupira-js-sdk/examples/`.

## Segurança { #security }

Extensões de terceiros rodam com os privilégios do seu usuário. Subprocessos não são um
sandbox. Não instale pacotes não confiáveis. O Curupira nunca instala pacotes
durante a descoberta; os comandos de instalação pedem confirmação, a menos que `--yes` seja usado.
