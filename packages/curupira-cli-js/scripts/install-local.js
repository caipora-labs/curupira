#!/usr/bin/env node
"use strict";

const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

/**
 * Install the locally packed, self-contained Curupira CLI tarball.
 */
function main(argv) {
  const options = parseArgs(argv);
  const prefix = options.prefix;
  const mainTarball = options.main ? path.resolve(options.main) : null;
  if (!prefix || !mainTarball) {
    process.stderr.write("Usage: install-local.js --prefix DIR --main TARBALL\n");
    process.exit(1);
  }
  fs.rmSync(prefix, { recursive: true, force: true });
  fs.mkdirSync(prefix, { recursive: true });
  execFileSync(
    "npm",
    [
      "install",
      "--prefix",
      prefix,
      "--ignore-scripts",
      "--no-save",
      "--no-package-lock",
      "--offline",
      mainTarball,
    ],
    {
      stdio: "inherit",
      env: { ...process.env, npm_config_audit: "false", npm_config_fund: "false" },
    },
  );
  process.stdout.write(`${path.join(prefix, "node_modules", ".bin")}\n`);
}

/**
 * @param {string[]} argv
 * @returns {Record<string, string>}
 */
function parseArgs(argv) {
  /** @type {Record<string, string>} */
  const options = {};
  for (let index = 0; index < argv.length; index += 1) {
    const item = argv[index];
    if (!item.startsWith("--")) continue;
    options[item.slice(2)] = argv[index + 1] ?? "";
    index += 1;
  }
  return options;
}

if (require.main === module) {
  main(process.argv.slice(2));
}

module.exports = { main };
