"use strict";

const assert = require("node:assert/strict");
const { execFileSync, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { detectLibc } = require("../lib/launch.js");
const { selectTarget } = require("../lib/targets.js");
const { PACKAGE_ROOT } = require("../scripts/layout.js");

const REPO_ROOT = path.resolve(PACKAGE_ROOT, "../..");
const CORE = path.join(REPO_ROOT, "packages/curupira-core");

test("installs the local npm packages and runs the Rust CLI", { timeout: 600_000 }, () => {
  const libc = detectLibc(process.platform);
  const target = selectTarget(process.platform, process.arch, libc);
  assert.ok(target, `this runner has no npm target (${process.platform} ${process.arch} ${libc})`);
  const cargo = fs.readFileSync(path.join(CORE, "Cargo.toml"), "utf8");
  const version = cargo.match(/^version = "([^"]+)"/m)?.[1];
  assert.ok(version);

  // cwd is the crate so rustup reads its rust-toolchain.toml (stable).
  execFileSync("cargo", ["build", "--bins"], {
    cwd: CORE,
    stdio: "inherit",
  });
  const built = path.join(CORE, "target", "debug", process.platform === "win32" ? "curupira.exe" : "curupira");
  const stage = fs.mkdtempSync(path.join(os.tmpdir(), "curupira-npm-install-"));
  const assemble = path.join(PACKAGE_ROOT, "scripts/assemble.js");
  execFileSync(process.execPath, [assemble, "binary", "--bin", built, "--target", target.key, "--version", version, "--out", stage], {
    stdio: "inherit",
  });
  execFileSync(process.execPath, [assemble, "main", "--version", version, "--out", stage], { stdio: "inherit" });
  execFileSync(process.execPath, [assemble, "verify-one", "--dir", stage, "--target", target.key, "--version", version], {
    stdio: "inherit",
  });

  const packs = path.join(stage, "packs");
  fs.mkdirSync(packs);
  const mainTarball = npmPack(path.join(stage, "curupira"), packs);
  const platformTarball = npmPack(path.join(stage, target.packageName.split("/")[1]), packs);
  const prefix = path.join(stage, "prefix");
  execFileSync(
    process.execPath,
    [
      path.join(PACKAGE_ROOT, "scripts/install-local.js"),
      "--prefix",
      prefix,
      "--main",
      mainTarball,
      "--platform",
      platformTarball,
    ],
    { stdio: "inherit" },
  );

  const curupira = path.join(prefix, "node_modules", ".bin", "curupira");
  const curu = path.join(prefix, "node_modules", ".bin", "curu");
  const versionOut = execFileSync(curupira, ["--version"], { encoding: "utf8" });
  assert.equal(versionOut.trim(), `curupira ${version}`);
  const aliasOut = execFileSync(curu, ["--version"], { encoding: "utf8" });
  assert.equal(aliasOut.trim(), `curu ${version}`);
  const help = execFileSync(curupira, ["--help"], { encoding: "utf8" });
  assert.match(help, /Usage: curupira/);
  assert.match(help, /\bvalidate\b/);
  assert.match(help, /--watch/);
  assert.match(help, /\btui\b/);
  assert.match(help, /\bplugins\b/);
  const aliasHelp = execFileSync(curu, ["--help"], { encoding: "utf8" });
  assert.match(aliasHelp, /Usage: curu/);

  const rejected = spawnSync(curupira, ["run", "--watch", "--dry-run"], { encoding: "utf8" });
  assert.equal(rejected.status, 2);
  assert.match(rejected.stderr, /--dry-run cannot be combined with --watch/);

  const home = fs.mkdtempSync(path.join(stage, "home-"));
  const configDir = path.join(home, ".curupira");
  fs.mkdirSync(configDir);
  const settings = minimalSettings();
  const settingsPath = path.join(configDir, "settings.toml");
  fs.writeFileSync(settingsPath, settings);
  const marker = path.join(configDir, "state.sqlite3");
  fs.writeFileSync(marker, "existing-state");
  const env = {
    ...process.env,
    HOME: home,
    USERPROFILE: home,
  };
  const validated = spawnSync(curupira, ["validate"], { env, encoding: "utf8" });
  assert.equal(validated.status, 0, validated.stderr);
  assert.match(validated.stdout, /Configuration is valid/);
  assert.equal(fs.readFileSync(settingsPath, "utf8"), settings);
  assert.equal(fs.readFileSync(marker, "utf8"), "existing-state");
  assert.equal(fs.existsSync(path.join(home, ".curupira-npm")), false);

  const listed = spawnSync(curupira, ["plugins", "list"], { env, encoding: "utf8" });
  assert.equal(listed.status, 0, listed.stderr);
  assert.match(listed.stdout, /cron\tcurupira/);

  const empty = path.join(stage, "empty-path");
  fs.mkdirSync(empty);
  const stripped = {
    HOME: home,
    USERPROFILE: home,
    PATH: empty,
    SystemRoot: process.env.SystemRoot,
  };
  const wrapper = path.join(prefix, "node_modules", "curupira", "bin", "curupira.js");
  const direct = spawnSync(process.execPath, [wrapper, "--version"], { env: stripped, encoding: "utf8" });
  assert.equal(direct.status, 0, direct.stderr);
  assert.equal(direct.stdout.trim(), `curupira ${version}`);

  const npxConfig = path.join(configDir, "npx.toml");
  fs.writeFileSync(npxConfig, extensionSettings("npx", '["--yes", "@example/ext"]'));
  const missingNpx = spawnSync(process.execPath, [wrapper, "--config", npxConfig, "validate"], {
    env: stripped,
    encoding: "utf8",
  });
  assert.notEqual(missingNpx.status, 0);
  assert.match(missingNpx.stderr, /npx/);
  assert.match(missingNpx.stderr, /Node\.js/);
  assert.match(missingNpx.stderr, /not found on PATH/);

  const uvxConfig = path.join(configDir, "uvx.toml");
  fs.writeFileSync(uvxConfig, extensionSettings("uvx", '["--from", "curupira-plugins", "curupira-plugins"]'));
  const missingUvx = spawnSync(process.execPath, [wrapper, "--config", uvxConfig, "validate"], {
    env: stripped,
    encoding: "utf8",
  });
  assert.notEqual(missingUvx.status, 0);
  assert.match(missingUvx.stderr, /uvx/);
  assert.match(missingUvx.stderr, /not found on PATH/);
});

/**
 * @param {string} directory
 * @param {string} destination
 * @returns {string}
 */
function npmPack(directory, destination) {
  const output = execFileSync("npm", ["pack", "--json", "--pack-destination", destination], {
    cwd: directory,
    encoding: "utf8",
  });
  const packed = JSON.parse(output);
  return path.join(destination, packed[0].filename);
}

/**
 * @returns {string}
 */
function minimalSettings() {
  return `[settings]
max_active_tasks = 1
workspace_dir = "~/.curupira/workspaces"
state_db_path = "~/.curupira/state.sqlite3"

[repositories.local]
remote = "https://github.com/acme/api.git"

[agents.defaults]
profile = "cursor"
timezone = "UTC"

[agents.profiles.cursor]
provider = "cursor"

[automations.nightly]
repository = "local"
trigger_type = "cron"
schedule = "0 0 * * *"
prompt = "status"
`;
}

/**
 * @param {string} launcher
 * @param {string} args
 * @returns {string}
 */
function extensionSettings(launcher, args) {
  return `${minimalSettings()}
[plugins.ext]
type = "${launcher}"
args = ${args}

[automations.demo]
repository = "local"
trigger_type = "ext/sample"
prompt = "status"
`;
}
