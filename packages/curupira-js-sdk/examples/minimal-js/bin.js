#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import { runExtension } from "@caipora-labs/curupira-sdk";

import triggers from "./index.js";

const here = dirname(fileURLToPath(import.meta.url));
const pkg = JSON.parse(readFileSync(join(here, "package.json"), "utf8"));

const MANIFEST = `
manifest_version = 1
name = "curupira-example-js"
version = "{version}"
protocol_version = 2
runtime = "node"
kind = "trigger"
trigger_types = ["github-issue"]

[launch]
type = "npx"
package = "@caipora-labs/curupira-example-js"
version = "{version}"

[package]
source = "npm"
name = "@caipora-labs/curupira-example-js"
version = "{version}"
`.trim();

await runExtension(triggers, {
  name: pkg.name,
  version: pkg.version,
  manifestTemplate: MANIFEST,
});
