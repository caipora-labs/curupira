"use strict";

const assert = require("node:assert/strict");
const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { detectLibc, prepare } = require("../lib/launch.js");
const { TARGETS } = require("../lib/targets.js");
const { installFixture, waitForFile } = require("../scripts/layout.js");

/**
 * @returns {string}
 */
function tempRoot() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "curupira-npm-"));
}

test("selects the host platform package and forwards argv0 without a shell", () => {
  const root = tempRoot();
  const fixture = installFixture(root, { platform: "linux", arch: "x64", libc: "glibc" });
  const prepared = prepare({
    packageRoot: fixture.mainDir,
    platform: "linux",
    arch: "x64",
    libc: "glibc",
    argv0: "curu",
    args: ["--config", "my settings.toml", "validate"],
  });
  assert.equal("error" in prepared, false);
  if ("error" in prepared) return;
  assert.equal(prepared.spawnOptions.shell, false);
  assert.equal(prepared.spawnOptions.stdio, "inherit");
  assert.equal(prepared.spawnOptions.argv0, "curu");
  assert.equal(prepared.spawnOptions.env, undefined);
  assert.equal(prepared.spawnOptions.cwd, undefined);
  assert.deepEqual(prepared.args, ["--config", "my settings.toml", "validate"]);
  assert.equal(path.basename(prepared.bin), "curupira");
  assert.match(prepared.bin, /curupira-linux-x64/);
});

test("resolves a binary path that contains spaces", () => {
  const root = tempRoot();
  const spaced = path.join(root, "dir with spaces");
  const fixture = installFixture(spaced, { platform: "linux", arch: "x64", libc: "glibc" });
  const prepared = prepare({
    packageRoot: fixture.mainDir,
    platform: "linux",
    arch: "x64",
    libc: "glibc",
    argv0: "curupira",
    args: ["--version"],
  });
  assert.equal("error" in prepared, false);
  if ("error" in prepared) return;
  assert.match(prepared.bin, /dir with spaces/);
  const result = spawnSync(prepared.bin, ["args", "--config", "my file.toml"], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), ["args", "--config", "my file.toml"]);
});

test("forwards arguments, stdio, and the exit code", () => {
  const root = tempRoot();
  const fixture = installFixture(root);
  const args = spawnSync(fixture.wrapper, ["args", "--config", "a b.toml", "run", "--watch"], {
    encoding: "utf8",
  });
  assert.equal(args.status, 0);
  assert.deepEqual(JSON.parse(args.stdout), ["args", "--config", "a b.toml", "run", "--watch"]);

  const exited = spawnSync(fixture.wrapper, ["exit", "7"], { encoding: "utf8" });
  assert.equal(exited.status, 7);

  const stdio = spawnSync(fixture.wrapper, ["stdio"], { input: "hello", encoding: "utf8" });
  assert.equal(stdio.status, 0);
  assert.equal(stdio.stdout, "out:hello");
  assert.equal(stdio.stderr, "err:hello");
});

test("curu and curupira are both installed commands", () => {
  const root = tempRoot();
  const fixture = installFixture(root, { platform: "linux", arch: "x64", libc: "glibc" });
  const manifest = JSON.parse(fs.readFileSync(path.join(fixture.mainDir, "package.json"), "utf8"));
  assert.equal(manifest.bin.curupira, "./bin/curupira.js");
  assert.equal(manifest.bin.curu, "./bin/curu.js");
  const alias = prepare({
    packageRoot: fixture.mainDir,
    platform: "linux",
    arch: "x64",
    libc: "glibc",
    argv0: "curu",
    args: [],
  });
  const command = prepare({
    packageRoot: fixture.mainDir,
    platform: "linux",
    arch: "x64",
    libc: "glibc",
    argv0: "curupira",
    args: [],
  });
  assert.equal("error" in alias || "error" in command, false);
  if ("error" in alias || "error" in command) return;
  assert.equal(alias.bin, command.bin);
  assert.equal(alias.spawnOptions.argv0, "curu");
  assert.equal(command.spawnOptions.argv0, "curupira");
});

test("forwards SIGTERM and exits with the child status", async () => {
  if (process.platform === "win32") return;
  const root = tempRoot();
  const fixture = installFixture(root);
  const ready = path.join(root, "ready");
  const child = spawn(fixture.wrapper, ["sleep", ready], { stdio: "ignore" });
  await waitForFile(ready);
  const exited = new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("wrapper did not exit")), 3000);
    child.on("exit", (code, signal) => {
      clearTimeout(timer);
      resolve({ code, signal });
    });
  });
  process.kill(child.pid, "SIGTERM");
  const result = await exited;
  assert.equal(result.code, 42);
  assert.equal(result.signal, null);
});

test("reports an unsupported platform", () => {
  const root = tempRoot();
  const fixture = installFixture(root, { omitPlatform: true });
  const prepared = prepare({
    packageRoot: fixture.mainDir,
    platform: "sunos",
    arch: "x64",
    libc: null,
    argv0: "curupira",
    args: [],
  });
  assert.equal("error" in prepared, true);
  if (!("error" in prepared)) return;
  assert.match(prepared.error, /no npm binary for sunos x64/);
  assert.match(prepared.error, /linux-x64/);
  assert.match(prepared.error, /win32-arm64/);
  const result = spawnSync(fixture.wrapper, ["--version"], { encoding: "utf8" });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /no npm binary|platform package/);
});

test("reports a missing platform package for a supported target", () => {
  const root = tempRoot();
  const fixture = installFixture(root, { omitPlatform: true });
  const prepared = prepare({
    packageRoot: fixture.mainDir,
    platform: "darwin",
    arch: "arm64",
    libc: null,
    argv0: "curupira",
    args: [],
  });
  assert.equal("error" in prepared, true);
  if (!("error" in prepared)) return;
  assert.match(prepared.error, /@caipora-labs\/curupira-darwin-arm64 is not installed/);
});

test("reports a missing binary inside the platform package", () => {
  const root = tempRoot();
  const fixture = installFixture(root, { platform: "linux", arch: "x64", libc: "glibc" });
  fs.rmSync(path.join(fixture.platformDir, "bin", "curupira"));
  const prepared = prepare({
    packageRoot: fixture.mainDir,
    platform: "linux",
    arch: "x64",
    libc: "glibc",
    argv0: "curupira",
    args: [],
  });
  assert.equal("error" in prepared, true);
  if (!("error" in prepared)) return;
  assert.match(prepared.error, /binary is missing/);
});

test("reports a wrapper and platform version mismatch", () => {
  const root = tempRoot();
  const fixture = installFixture(root, {
    platform: "linux",
    arch: "x64",
    libc: "glibc",
    mainVersion: "0.2.0",
    platformVersion: "0.9.0",
  });
  const prepared = prepare({
    packageRoot: fixture.mainDir,
    platform: "linux",
    arch: "x64",
    libc: "glibc",
    argv0: "curupira",
    args: [],
  });
  assert.equal("error" in prepared, true);
  if (!("error" in prepared)) return;
  assert.match(prepared.error, /wrapper 0\.2\.0 does not match @caipora-labs\/curupira-linux-x64 0\.9\.0/);
});

test("reports a failure to execute the binary", () => {
  const root = tempRoot();
  const fixture = installFixture(root);
  fs.chmodSync(path.join(fixture.platformDir, "bin", "curupira"), 0o000);
  const result = spawnSync(fixture.wrapper, ["--version"], { encoding: "utf8" });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Failed to start Curupira binary/);
});

test("uses the Windows executable name", () => {
  const root = tempRoot();
  const fixture = installFixture(root, {
    platform: "win32",
    arch: "arm64",
    libc: null,
    binary: Buffer.from([0x4d, 0x5a, 0, 0]),
  });
  const prepared = prepare({
    packageRoot: fixture.mainDir,
    platform: "win32",
    arch: "arm64",
    libc: null,
    argv0: "curupira",
    args: ["--help"],
  });
  assert.equal("error" in prepared, false);
  if ("error" in prepared) return;
  assert.equal(path.basename(prepared.bin), "curupira.exe");
});

test("distinguishes glibc and musl packages", () => {
  assert.equal(
    require("../lib/targets.js").selectTarget("linux", "x64", "musl")?.packageName,
    "@caipora-labs/curupira-linux-x64-musl",
  );
  assert.equal(
    require("../lib/targets.js").selectTarget("linux", "arm64", "glibc")?.packageName,
    "@caipora-labs/curupira-linux-arm64",
  );
  assert.equal(require("../lib/targets.js").selectTarget("linux", "ia32", "glibc"), null);
  assert.equal(detectLibc("darwin"), null);
  assert.equal(
    detectLibc("linux", () => ({ header: { glibcVersionRuntime: "2.35" }, sharedObjects: [] })),
    "glibc",
  );
  assert.equal(
    detectLibc("linux", () => ({ sharedObjects: ["/lib/ld-musl-x86_64.so.1"] })),
    "musl",
  );
  assert.equal(
    detectLibc(
      "linux",
      () => null,
      (file) => file.endsWith("ld-musl-aarch64.so.1"),
    ),
    "musl",
  );
});

test("every published target has a distinct package name", () => {
  const names = new Set(TARGETS.map((target) => target.packageName));
  assert.equal(names.size, TARGETS.length);
  assert.equal(names.has("curupira"), false);
});
