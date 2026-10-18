"use strict";

const fs = require("node:fs");
const path = require("node:path");
const zlib = require("node:zlib");

const PACKAGE_ROOT = path.resolve(__dirname, "..");

const FAKE_BINARY = `#!/usr/bin/env node
"use strict";
const fs = require("node:fs");
const [cmd, extra] = process.argv.slice(2);
if (cmd === "args") {
  process.stdout.write(JSON.stringify(process.argv.slice(2)));
  process.exit(0);
}
if (cmd === "exit") process.exit(Number(extra));
if (cmd === "stdio") {
  const chunks = [];
  process.stdin.on("data", (chunk) => chunks.push(chunk));
  process.stdin.on("end", () => {
    const data = Buffer.concat(chunks);
    process.stdout.write(Buffer.concat([Buffer.from("out:"), data]));
    process.stderr.write(Buffer.concat([Buffer.from("err:"), data]));
    process.exit(0);
  });
  return;
}
if (cmd === "sleep") {
  fs.writeFileSync(extra, "ready");
  process.on("SIGTERM", () => process.exit(42));
  setInterval(() => {}, 1000);
  return;
}
process.stderr.write("unknown\\n");
process.exit(2);
`;

/**
 * @param {string} root
 * @param {{
 *   platform?: string,
 *   arch?: string,
 *   libc?: string | null,
 *   mainVersion?: string,
 *   platformVersion?: string,
 *   binary?: Buffer | string,
 *   omitPlatform?: boolean,
 * }} [options]
 * @returns {{ mainDir: string, wrapper: string, alias: string, platformDir: string | null }}
 */
function installFixture(root, options = {}) {
  const platform = options.platform ?? "linux";
  const arch = options.arch ?? "x64";
  const libc = options.libc === undefined ? "glibc" : options.libc;
  const mainVersion = options.mainVersion ?? "0.2.0";
  const platformVersion = options.platformVersion ?? mainVersion;
  const { selectTarget, packageDirectory, binaryFileName } = require("../lib/targets.js");
  const target = selectTarget(platform, arch, libc);
  const mainDir = path.join(root, "node_modules", "@caipora", "curupira");
  fs.mkdirSync(mainDir, { recursive: true });
  fs.cpSync(path.join(PACKAGE_ROOT, "bin"), path.join(mainDir, "bin"), { recursive: true });
  fs.cpSync(path.join(PACKAGE_ROOT, "lib"), path.join(mainDir, "lib"), { recursive: true });
  fs.chmodSync(path.join(mainDir, "bin", "curupira.js"), 0o755);
  fs.chmodSync(path.join(mainDir, "bin", "curu.js"), 0o755);
  const manifest = JSON.parse(fs.readFileSync(path.join(PACKAGE_ROOT, "package.json"), "utf8"));
  manifest.version = mainVersion;
  fs.writeFileSync(path.join(mainDir, "package.json"), JSON.stringify(manifest));
  if (options.omitPlatform || target === null) {
    return {
      mainDir,
      wrapper: path.join(mainDir, "bin", "curupira.js"),
      alias: path.join(mainDir, "bin", "curu.js"),
      platformDir: null,
    };
  }
  const platformDir = path.join(root, "node_modules", "@caipora", packageDirectory(target.packageName));
  const binDir = path.join(platformDir, "bin");
  fs.mkdirSync(binDir, { recursive: true });
  const binary = path.join(binDir, binaryFileName(platform));
  const payload = options.binary ?? FAKE_BINARY;
  fs.writeFileSync(binary, payload);
  fs.chmodSync(binary, 0o755);
  fs.writeFileSync(
    path.join(platformDir, "package.json"),
    JSON.stringify({
      name: target.packageName,
      version: platformVersion,
      os: [target.os],
      cpu: [target.cpu],
    }),
  );
  return {
    mainDir,
    wrapper: path.join(mainDir, "bin", "curupira.js"),
    alias: path.join(mainDir, "bin", "curu.js"),
    platformDir,
  };
}

/**
 * Build a ZIP archive. `method` 0 stores bytes; `method` 8 deflates them.
 *
 * @param {{ name: string, data: Buffer, method?: number }[]} entries
 * @returns {Buffer}
 */
function zipEntries(entries) {
  /** @type {Buffer[]} */
  const locals = [];
  /** @type {Buffer[]} */
  const centrals = [];
  let offset = 0;
  for (const entry of entries) {
    const name = Buffer.from(entry.name);
    const method = entry.method ?? 0;
    const stored = method === 8 ? zlib.deflateRawSync(entry.data) : entry.data;
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(method, 8);
    local.writeUInt32LE(stored.length, 18);
    local.writeUInt32LE(entry.data.length, 22);
    local.writeUInt16LE(name.length, 26);
    locals.push(local, name, stored);
    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(20, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt16LE(method, 10);
    central.writeUInt32LE(stored.length, 20);
    central.writeUInt32LE(entry.data.length, 24);
    central.writeUInt16LE(name.length, 28);
    central.writeUInt32LE(offset, 42);
    centrals.push(Buffer.concat([central, name]));
    offset += 30 + name.length + stored.length;
  }
  const centralDirectory = Buffer.concat(centrals);
  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(entries.length, 8);
  eocd.writeUInt16LE(entries.length, 10);
  eocd.writeUInt32LE(centralDirectory.length, 12);
  eocd.writeUInt32LE(offset, 16);
  return Buffer.concat([...locals, centralDirectory, eocd]);
}

/**
 * @param {string} file
 * @param {number} [timeoutMs]
 * @returns {Promise<void>}
 */
async function waitForFile(file, timeoutMs = 3000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (fs.existsSync(file)) return;
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
  throw new Error(`timed out waiting for ${file}`);
}

module.exports = {
  FAKE_BINARY,
  PACKAGE_ROOT,
  installFixture,
  waitForFile,
  zipEntries,
};
