"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");

const { TARGETS } = require("../lib/targets.js");
const { PACKAGE_ROOT } = require("../scripts/layout.js");

const REPO_ROOT = path.resolve(PACKAGE_ROOT, "../..");

test("the scoped wrapper is one self-contained package with no install-time compiler", () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(PACKAGE_ROOT, "package.json"), "utf8"));
  assert.equal(manifest.name, "@caipora-labs/curupira");
  assert.equal(manifest.dependencies, undefined);
  assert.equal(manifest.optionalDependencies, undefined);
  assert.equal(manifest.scripts.preinstall, undefined);
  assert.equal(manifest.scripts.install, undefined);
  assert.equal(manifest.scripts.postinstall, undefined);
  assert.equal(manifest.bin.curupira, "./bin/curupira.js");
  assert.equal(manifest.bin.curu, "./bin/curu.js");
  assert.deepEqual(
    manifest.os,
    ["linux", "darwin", "win32"],
  );
  assert.deepEqual(manifest.cpu, ["x64", "arm64"]);
  const cargo = fs.readFileSync(path.join(REPO_ROOT, "packages/curupira-core/Cargo.toml"), "utf8");
  const version = cargo.match(/^version = "([^"]+)"/m);
  assert.ok(version);
  assert.equal(manifest.version, version[1]);
  const launch = fs.readFileSync(path.join(PACKAGE_ROOT, "lib/launch.js"), "utf8");
  assert.equal(launch.includes("shell: true"), false);
  assert.equal(launch.includes("cargo"), false);
  assert.equal(launch.includes("python"), false);
  assert.equal(launch.includes("pip "), false);
});

test("publish workflow targets match the npm platform list", () => {
  const workflow = fs.readFileSync(path.join(REPO_ROOT, ".github/workflows/publish.yml"), "utf8");
  assert.match(workflow, /tags:\s*\n\s+- "publish\/\*\*"/);
  assert.doesNotMatch(workflow, /workflow_dispatch|publish_npm/);
  for (const target of TARGETS) {
    assert.match(workflow, new RegExp(`npm_target: ${target.key}\\b`));
  }
  assert.match(workflow, /npm pack --pack-destination dist-npm \.\/npm-stage\/curupira/);
  assert.match(workflow, /dist-npm\/caipora-labs-curupira-\$\{VERSION\}\.tgz/);
  assert.match(workflow, /npm publish dist-npm\/caipora-labs-curupira-\*\.tgz/);
  assert.doesNotMatch(workflow, /dist-npm\/platform|Publish platform packages/);
  assert.doesNotMatch(workflow, /vars\.NPM_|NPM_OIDC_READY|NPM_MANUAL_BOOTSTRAP_VERSION/);
  assert.doesNotMatch(workflow, /NPM_BOOTSTRAP_TOKEN|NODE_AUTH_TOKEN|workflow_dispatch/);
});

test("LICENSE matches the repository license", () => {
  assert.equal(
    fs.readFileSync(path.join(PACKAGE_ROOT, "LICENSE"), "utf8"),
    fs.readFileSync(path.join(REPO_ROOT, "LICENSE"), "utf8"),
  );
});
