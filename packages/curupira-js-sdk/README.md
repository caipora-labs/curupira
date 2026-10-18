# `@caipora-labs/curupira-sdk`

Declarative Node.js SDK for [Curupira](https://github.com/caipora-labs/curupira)
process extensions. Register trigger functions with a plain object, return a
serializable object or `null`, and let the SDK speak protocol **2** (JSON-RPC
over length-prefixed stdin/stdout) with the Rust CLI.

## Install

```bash
npm install @caipora-labs/curupira-sdk
```

Requires **Node.js 20+**. The Curupira CLI launches published plugins with
`npx` (no global install).

## Declare triggers

### JavaScript + JSDoc

```js
import { defineTriggers } from "@caipora-labs/curupira-sdk";

/**
 * @typedef {Object} GitHubIssueParams
 * @property {string} repo
 * @property {string[]} [labels]
 */

/**
 * @param {GitHubIssueParams} params
 */
async function githubIssue({ repo, labels = [] }) {
  return { repo, labels, title: "Fix authentication" };
}

export default defineTriggers({
  githubIssue,
});
```

JSDoc is for editors only. It is not validated at runtime.

### TypeScript

```ts
import { defineTriggers } from "@caipora-labs/curupira-sdk";

export default defineTriggers({
  githubIssue: async (params: { repo: string; labels?: string[] }) => ({
    repo: params.repo,
    labels: params.labels ?? [],
  }),
});
```

The property name becomes the local trigger id in kebab-case
(`githubIssue` → `github-issue`). Automations address it as
`<plugins-alias>/github-issue` after you register the package under
`[plugins.<alias>]`.

## Plugin bin

Ship a `package.json` `bin` that starts the protocol runtime:

```js
#!/usr/bin/env node
import { runExtension } from "@caipora-labs/curupira-sdk";
import triggers from "./index.js";

await runExtension(triggers, {
  name: "@acme/curupira-ext",
  version: "1.2.0",
  manifestTemplate: `...optional TOML with {version}...`,
});
```

Publish the package to npm. End users do **not** install it globally. Curupira
runs it as:

```bash
npx --yes @acme/curupira-ext@1.2.0
```

Settings:

```toml
[plugins.acme]
type = "npx"
args = ["--yes", "@acme/curupira-ext@1.2.0"]
tools = ["*"]

[automations.demo]
trigger_type = "acme/github-issue"
repository = "api"
repo = "acme/api"
prompt = "Handle ${title} in ${repo}"
```

## Return values

| Return | Protocol `values` |
| --- | --- |
| `null` / `undefined` | `null` (nothing found; ends the poll round) |
| `{}` | `[]` (an item with no pairs) |
| `{ a: 1, b: true }` | `[{ "key": "a", "value": "1" }, { "key": "b", "value": "true" }]` |

Nested objects and arrays become compact JSON strings (`sort_keys` for objects).
Top-level arrays/scalars, bad placeholder keys, and non-serializable values raise
errors (JSON-RPC `-32002`), not `null`.

Do not put core automation fields (`trigger_type`, `repository`, `prompt`,
`profile`, `checkout`) on the trigger parameter object — use names like `repo`.

## Modules

This package is **ESM** (`"type": "module"`). Publish compiled JavaScript (and
`.d.ts` if you author in TypeScript). Curupira does not compile TypeScript for
you at launch time.

## Examples

See `examples/minimal-js` and `examples/minimal-ts` in this directory, and the
guide in `docs/en/extensions.md`.
