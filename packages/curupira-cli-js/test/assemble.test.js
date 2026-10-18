"use strict";

const assert = require("node:assert/strict");
const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  stageBinary,
  stageFromWheel,
  stageMain,
  verifyAll,
  verifyOne,
  verifyTarballs,
} = require("../scripts/assemble.js");
const { TARGETS } = require("../lib/targets.js");
const { zipEntries } = require("../scripts/layout.js");

const ELF = Buffer.from([0x7f, 0x45, 0x4c, 0x46, 0, 0, 0, 0]);
const PE = Buffer.from([0x4d, 0x5a, 0, 0]);

/**
 * @returns {string}
 */
function tempRoot() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "curupira-assemble-"));
}

test("stages a native binary for later inclusion in the single package", () => {
  const root = tempRoot();
  const bin = path.join(root, "curupira");
  fs.writeFileSync(bin, ELF);
  const out = path.join(root, "stage");
  stageBinary({ bin, target: "linux-arm64", version: "1.2.3", out });
  verifyOne(out, "linux-arm64", "1.2.3");
  const mode = fs.statSync(path.join(out, "binaries", "linux-arm64", "curupira")).mode;
  assert.equal(mode & 0o111, 0o111);
});

test("rejects a script where a native binary is required", () => {
  const root = tempRoot();
  const bin = path.join(root, "curupira");
  fs.writeFileSync(bin, "#!/bin/sh\necho no\n");
  assert.throws(
    () => stageBinary({ bin, target: "linux-x64", version: "0.2.0", out: path.join(root, "stage") }),
    /not an ELF, Mach-O, or PE/,
  );
});

test("extracts the native binary from a wheel and ignores script entry points", () => {
  const root = tempRoot();
  const wheel = path.join(root, "curupira.whl");
  fs.writeFileSync(
    wheel,
    zipEntries([
      { name: "curupira-0.2.0.data/scripts/curupira", data: Buffer.from("#!/usr/bin/env python3\n") },
      {
        name: "curupira-0.2.0.data/scripts/curupira.exe",
        data: PE,
        method: 8,
      },
      { name: "curupira-0.2.0.data/scripts/curu", data: ELF },
    ]),
  );
  const out = path.join(root, "stage");
  stageFromWheel({ wheel, target: "win32-x64", version: "0.2.0", out });
  verifyOne(out, "win32-x64", "0.2.0");
  const packed = fs.readFileSync(path.join(out, "binaries", "win32-x64", "curupira.exe"));
  assert.equal(packed.subarray(0, 2).toString(), "MZ");
});

test("refuses a wheel that escapes its output directory", () => {
  const root = tempRoot();
  const wheel = path.join(root, "escape.whl");
  fs.writeFileSync(wheel, zipEntries([{ name: "../curupira", data: ELF }]));
  assert.throws(
    () => stageFromWheel({ wheel, target: "linux-x64", version: "0.2.0", out: path.join(root, "stage") }),
    /Unsafe ZIP path/,
  );
});

test("the single package bundles every platform binary", () => {
  const root = tempRoot();
  const out = path.join(root, "stage");
  for (const target of TARGETS) {
    const bin = path.join(root, `${target.key}.bin`);
    fs.writeFileSync(bin, target.os === "win32" ? PE : ELF);
    stageBinary({ bin, target: target.key, version: "9.9.9-dev0", out });
  }
  stageMain({ version: "9.9.9-dev0", out });
  verifyAll(out, "9.9.9-dev0");
  const main = JSON.parse(fs.readFileSync(path.join(out, "curupira", "package.json"), "utf8"));
  assert.equal(main.name, "@caipora-labs/curupira");
  assert.equal(main.version, "9.9.9-dev0");
  assert.equal(main.scripts, undefined);
  assert.equal(main.optionalDependencies, undefined);
  for (const target of TARGETS) {
    const binary = path.join(
      out,
      "curupira",
      "bin",
      "platforms",
      target.key,
      target.os === "win32" ? "curupira.exe" : "curupira",
    );
    assert.equal(fs.existsSync(binary), true);
  }
  assert.deepEqual(fs.readdirSync(out), ["curupira"]);
  assert.equal(fs.existsSync(path.join(out, "curupira", "bin", "curu.js")), true);
  assert.equal(fs.existsSync(path.join(out, "curupira", "test")), false);
});

test("verify-tarballs requires one complete scoped package at the release version", () => {
  const root = tempRoot();
  const stage = path.join(root, "stage");
  for (const target of TARGETS) {
    const bin = path.join(root, `${target.key}.bin`);
    fs.writeFileSync(bin, target.os === "win32" ? PE : ELF);
    stageBinary({ bin, target: target.key, version: "1.2.3", out: stage });
  }
  stageMain({ version: "1.2.3", out: stage });
  fs.cpSync(path.join(stage, "curupira"), path.join(root, "package"), { recursive: true });
  execFileSync("tar", ["-czf", path.join(root, "caipora-labs-curupira-1.2.3.tgz"), "-C", root, "package"]);
  verifyTarballs(root, "1.2.3");
  assert.throws(() => verifyTarballs(root, "9.9.9", "1"), /1\.2\.3/);
});

test("single-package assembly rejects a missing platform binary", () => {
  const root = tempRoot();
  const out = path.join(root, "stage");
  const bin = path.join(root, "curupira");
  fs.writeFileSync(bin, ELF);
  stageBinary({ bin, target: "linux-x64", version: "1.0.0", out });
  assert.throws(() => stageMain({ version: "1.0.0", out }), /not an ELF, Mach-O, or PE/);
});
