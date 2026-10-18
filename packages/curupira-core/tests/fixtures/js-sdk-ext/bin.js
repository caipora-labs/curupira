#!/usr/bin/env node
import { runExtension } from "@caipora/curupira-sdk";
import triggers from "./index.js";

const MANIFEST = `
manifest_version = 1
name = "curupira-js-sdk-ext-fixture"
version = "0.0.1"
protocol_version = 2
runtime = "node"
kind = "trigger"
trigger_types = ["sample-trigger", "sync-trigger"]

[launch]
type = "npx"
package = "curupira-js-sdk-ext-fixture"

[package]
source = "npm"
name = "curupira-js-sdk-ext-fixture"
version = "0.0.1"
`.trim();

await runExtension(triggers, {
  name: "curupira-js-sdk-ext-fixture",
  version: "0.0.1",
  manifestTemplate: MANIFEST,
});
