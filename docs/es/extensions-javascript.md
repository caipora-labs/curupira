# SDK de JavaScript y TypeScript

`@caipora-labs/curupira-sdk` convierte funciones comunes en triggers de Curupira para Node.js 20+.
Tu paquete declara un `bin` de npm, y Curupira inicia el paquete publicado con `npx`: nadie
instala tu plugin ni el SDK de forma global.

## Instalar { #install }

```sh
npm install @caipora-labs/curupira-sdk
```

El paquete es ESM. Publica JavaScript compilado, más archivos `.d.ts` si escribes
TypeScript; Curupira no transpila TypeScript cuando inicia un plugin.

## Un trigger mínimo { #minimal-trigger }

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
      // Devuelve un objeto, o null cuando no se encontró nada.
      return { repo, labels, title: "Fix authentication" };
    }

    export default defineTriggers({
      githubIssue,
    });
    ```

    JSDoc ayuda a los editores. No se lee en tiempo de ejecución.

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

El nombre de la propiedad es el nombre local del trigger en kebab-case: `githubIssue` se
convierte en `github-issue`.

## El entrypoint `bin` { #bin }

```js
#!/usr/bin/env node
import { runExtension } from "@caipora-labs/curupira-sdk";
import triggers from "./index.js";

await runExtension(triggers, {
  name: "@acme/curupira-ext",
  version: "1.2.0",
  // Opcional: se imprime para `--curupira-print-manifest`
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

Declara el ejecutable en `package.json`:

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

## Usarlo desde los ajustes { #settings }

Publica en npm y luego registra el lanzador con una versión fija:

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

Curupira ejecuta `npx --yes @acme/curupira-ext@1.2.0` como argumentos separados (nunca como
una cadena de shell), usa stdin y stdout para los frames del protocolo y deja stderr para
tus logs. Se aplica la caché normal de npm. Si falta `npx`, `curupira validate` te indica
que instales Node.js.

## Reglas { #rules }

- Se admiten funciones síncronas y asíncronas.
- Devuelve **un** objeto simple o `null`. El SDK convierte el objeto en
  `{ "values": [{ "key", "value" }, ...] }`; `null` se convierte en `{ "values": null }`, y
  un objeto vacío en `{ "values": [] }`.
- No construyas la lista de pares a mano ni devuelvas un array de elementos.
- Los valores anidados siguen las mismas reglas de serialización que el
  [SDK de Python](extensions-python.md#serialization).
- Los campos principales de la automatización (`trigger_type`, `repository`, `prompt`,
  `profile`, `checkout`) no son parámetros del trigger. Usa `repo` o un nombre similar para
  los ids de la forja.
- Los flags de polling (`preview`, `limit`) no se pasan a la función.

Ejemplos en el repositorio:

- `packages/curupira-js-sdk/examples/`: ejemplos completos del SDK.
- `packages/curupira-core/tests/fixtures/node-ext/` y `ts-ext/`: fixtures del protocolo
  sin el SDK.
