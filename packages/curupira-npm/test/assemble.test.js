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

test("stages a native binary into the platform package", () => {
  const root = tempRoot();
  const bin = path.join(root, "curupira");
  fs.writeFileSync(bin, ELF);
  const out = path.join(root, "stage");
  stageBinary({ bin, target: "linux-arm64", version: "1.2.3", out });
  verifyOne(out, "linux-arm64", "1.2.3");
  const manifest = JSON.parse(
    fs.readFileSync(path.join(out, "curupira-linux-arm64", "package.json"), "utf8"),
  );
  assert.equal(manifest.libc[0], "glibc");
  assert.equal(manifest.os[0], "linux");
  assert.equal(manifest.cpu[0], "arm64");
  assert.equal(fs.existsSync(path.join(out, "curupira-linux-arm64", "LICENSE")), true);
  const mode = fs.statSync(path.join(out, "curupira-linux-arm64", "bin", "curupira")).mode;
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
  const packed = fs.readFileSync(path.join(out, "curupira-win32-x64", "bin", "curupira.exe"));
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

test("main package and every platform package share one version", () => {
  const root = tempRoot();
  const out = path.join(root, "stage");
  stageMain({ version: "9.9.9-dev0", out });
  for (const target of TARGETS) {
    const bin = path.join(root, `${target.key}.bin`);
    fs.writeFileSync(bin, target.os === "win32" ? PE : ELF);
    stageBinary({ bin, target: target.key, version: "9.9.9-dev0", out });
  }
  verifyAll(out, "9.9.9-dev0");
  const main = JSON.parse(fs.readFileSync(path.join(out, "curupira", "package.json"), "utf8"));
  assert.equal(main.version, "9.9.9-dev0");
  assert.equal(main.scripts, undefined);
  assert.deepEqual(Object.keys(main.optionalDependencies).sort(), TARGETS.map((target) => target.packageName).sort());
  assert.equal(fs.existsSync(path.join(out, "curupira", "bin", "curu.js")), true);
  assert.equal(fs.existsSync(path.join(out, "curupira", "test")), false);
});

test("verify-tarballs checks the packed package version", () => {
  const root = tempRoot();
  const packed = path.join(root, "package");
  fs.mkdirSync(packed);
  fs.writeFileSync(
    path.join(packed, "package.json"),
    JSON.stringify({ name: "@caipora/curupira-linux-x64", version: "1.2.3" }),
  );
  execFileSync("tar", ["-czf", path.join(root, "caipora-curupira-linux-x64-1.2.3.tgz"), "-C", root, "package"]);
  assert.throws(() => verifyTarballs(root, "1.2.3"), /Expected 9 npm tarballs/);
  verifyTarballs(root, "1.2.3", "1");
  assert.throws(() => verifyTarballs(root, "9.9.9", "1"), /1\.2\.3/);
});

test("verify rejects mixed versions", () => {
  const root = tempRoot();
  const out = path.join(root, "stage");
  stageMain({ version: "1.0.0", out });
  const bin = path.join(root, "curupira");
  fs.writeFileSync(bin, ELF);
  stageBinary({ bin, target: "linux-x64", version: "1.0.1", out });
  assert.throws(() => verifyAll(out, "1.0.0"), /1\.0\.1/);
});
