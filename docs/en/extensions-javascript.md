# JavaScript and TypeScript SDK

`@caipora-labs/curupira-sdk` turns plain functions into Curupira triggers for Node.js 20+.
Your package declares an npm `bin`, and Curupira starts the published package with `npx`:
nobody installs your plugin or the SDK globally.

## Install { #install }

```sh
npm install @caipora-labs/curupira-sdk
```

The package is ESM. Publish compiled JavaScript, plus `.d.ts` files if you write
TypeScript; Curupira does not transpile TypeScript when it starts a plugin.

## A minimal trigger { #minimal-trigger }

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
      // Return one object, or null when nothing was found.
      return { repo, labels, title: "Fix authentication" };
    }

    export default defineTriggers({
      githubIssue,
    });
    ```

    JSDoc helps editors. It is not read at runtime.

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

The property name is the local trigger name in kebab-case: `githubIssue` becomes
`github-issue`.

## The `bin` entrypoint { #bin }

```js
#!/usr/bin/env node
import { runExtension } from "@caipora-labs/curupira-sdk";
import triggers from "./index.js";

await runExtension(triggers, {
  name: "@acme/curupira-ext",
  version: "1.2.0",
  // Optional: printed for `--curupira-print-manifest`
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

Declare the executable in `package.json`:

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

## Use it from settings { #settings }

Publish to npm, then register the launcher with a pinned version:

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

Curupira runs `npx --yes @acme/curupira-ext@1.2.0` as separate arguments (never a shell
string), uses stdin and stdout for protocol frames, and leaves stderr for your logs. npm's
normal cache applies. If `npx` is missing, `curupira validate` says to install Node.js.

## Rules { #rules }

- Sync and async functions are both supported.
- Return **one** plain object or `null`. The SDK converts the object to
  `{ "values": [{ "key", "value" }, ...] }`; `null` becomes `{ "values": null }`, and an
  empty object becomes `{ "values": [] }`.
- Do not hand-build the pair list, and do not return an array of items.
- Nested values follow the same serialization rules as the
  [Python SDK](extensions-python.md#serialization).
- Core automation fields (`trigger_type`, `repository`, `prompt`, `profile`, `checkout`)
  are not trigger parameters. Use `repo` or a similar name for forge ids.
- Polling flags (`preview`, `limit`) are not passed into the function.

Examples in the repository:

- `packages/curupira-sdk-js/examples/`: complete SDK examples.
- `packages/curupira-cli/tests/fixtures/node-ext/` and `ts-ext/`: protocol fixtures
  without the SDK.
