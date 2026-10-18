# SDK JavaScript e TypeScript

O `@caipora-labs/curupira-sdk` transforma funções comuns em triggers do Curupira para Node.js 20+.
O seu pacote declara um `bin` do npm, e o Curupira inicia o pacote publicado com `npx`:
ninguém instala o seu plugin nem o SDK globalmente.

## Instalação { #install }

```sh
npm install @caipora-labs/curupira-sdk
```

O pacote é ESM. Publique JavaScript compilado, mais os arquivos `.d.ts` se você escrever
TypeScript; o Curupira não transpila TypeScript quando inicia um plugin.

## Um trigger mínimo { #minimal-trigger }

=== "JavaScript"

    ```js
    import { defineTriggers } from "@caipora-labs/curupira-sdk";

    /**
     * @typedef {Object} GitHubIssueParams
     * @property {string} repo
     * @property {string[]} [labels]
     */

    /** @param {GitHubIssueParams} params */
    async function githubIssue({ repo, labels = [] }) {
      // Retorne um objeto, ou null quando nada foi encontrado.
      return { repo, labels, title: "Fix authentication" };
    }

    export default defineTriggers({
      githubIssue,
    });
    ```

    O JSDoc ajuda os editores. Ele não é lido em tempo de execução.

=== "TypeScript"

    ```ts
    import { defineTriggers } from "@caipora-labs/curupira-sdk";

    export default defineTriggers({
      githubIssue: async (params: { repo: string; labels?: string[] }) => ({
        repo: params.repo,
        labels: params.labels ?? [],
        title: "Fix authentication",
      }),
    });
    ```

O nome da propriedade é o nome local do trigger em kebab-case: `githubIssue` vira
`github-issue`.

## O entrypoint `bin` { #bin }

```js
#!/usr/bin/env node
import { runExtension } from "@caipora-labs/curupira-sdk";
import triggers from "./index.js";

await runExtension(triggers, {
  name: "@acme/curupira-ext",
  version: "1.2.0",
  // Opcional: impresso para `--curupira-print-manifest`
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
    "@caipora-labs/curupira-sdk": "^0.1.0"
  }
}
```

## Use-o nas configurações { #settings }

Publique no npm e registre o launcher com uma versão fixada:

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

O Curupira executa `npx --yes @acme/curupira-ext@1.2.0` como argumentos separados (nunca uma string
de shell), usa stdin e stdout para os frames do protocolo e deixa o stderr para os seus logs. O
cache normal do npm se aplica. Se o `npx` estiver ausente, `curupira validate` pede que você instale o Node.js.

## Regras { #rules }

- Funções síncronas e assíncronas são suportadas.
- Retorne **um** objeto simples ou `null`. O SDK converte o objeto em
  `{ "values": [{ "key", "value" }, ...] }`; `null` vira `{ "values": null }`, e um
  objeto vazio vira `{ "values": [] }`.
- Não monte a lista de pares à mão e não retorne um array de itens.
- Valores aninhados seguem as mesmas regras de serialização do
  [SDK Python](extensions-python.md#serialization).
- Os campos centrais da automação (`trigger_type`, `repository`, `prompt`, `profile`, `checkout`)
  não são parâmetros do trigger. Use `repo` ou um nome parecido para ids da forge.
- As flags de consulta (`preview`, `limit`) não são passadas para a função.

Exemplos no repositório:

- `packages/curupira-js-sdk/examples/`: exemplos completos do SDK.
- `packages/curupira-core/tests/fixtures/node-ext/` e `ts-ext/`: fixtures do protocolo
  sem o SDK.
