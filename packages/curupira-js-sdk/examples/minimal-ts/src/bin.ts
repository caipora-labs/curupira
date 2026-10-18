#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { runExtension } from "@caipora/curupira-sdk";

import triggers from "./index.js";

const here = dirname(fileURLToPath(import.meta.url));
const pkg = JSON.parse(
  readFileSync(join(here, "..", "package.json"), "utf8"),
) as { name: string; version: string };

const MANIFEST = `
manifest_version = 1
name = "curupira-example-ts"
version = "{version}"
protocol_version = 2
runtime = "node"
kind = "trigger"
trigger_types = ["github-issue"]

[launch]
type = "npx"
package = "@caipora/curupira-example-ts"
version = "{version}"

[package]
source = "npm"
name = "@caipora/curupira-example-ts"
version = "{version}"
`.trim();

await runExtension(triggers, {
  name: pkg.name,
  version: pkg.version,
  manifestTemplate: MANIFEST,
});
