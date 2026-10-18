#!/usr/bin/env node
"use strict";

const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

/**
 * Install a locally packed `curupira` tarball and one platform tarball.
 *
 * Optional dependencies are omitted so npm does not contact the registry. The
 * platform tarball is extracted into `node_modules` the way npm would place it.
 */
function main(argv) {
  const options = parseArgs(argv);
  const prefix = options.prefix;
  const mainTarball = options.main;
  const platformTarball = options.platform;
  if (!prefix || !mainTarball || !platformTarball) {
    process.stderr.write(
      "Usage: install-local.js --prefix DIR --main TARBALL --platform TARBALL\n",
    );
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
      "--omit=optional",
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
  const extracted = fs.mkdtempSync(path.join(prefix, "extract-"));
  execFileSync("tar", ["-xzf", platformTarball, "-C", extracted], { stdio: "inherit" });
  const packed = path.join(extracted, "package");
  const manifest = JSON.parse(fs.readFileSync(path.join(packed, "package.json"), "utf8"));
  const scope = manifest.name.split("/")[0];
  if (!scope.startsWith("@")) throw new Error(`Expected a scoped platform package, got ${manifest.name}`);
  const scopeDir = path.join(prefix, "node_modules", scope);
  fs.mkdirSync(scopeDir, { recursive: true });
  const folder = String(manifest.name).split("/")[1];
  fs.renameSync(packed, path.join(scopeDir, folder));
  fs.rmSync(extracted, { recursive: true, force: true });
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
