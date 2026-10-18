#!/usr/bin/env node
"use strict";

const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const { TARGETS, binaryFileName } = require("../lib/targets.js");
const { unzip } = require("./unzip.js");

const PACKAGE_ROOT = path.resolve(__dirname, "..");
const REPO_ROOT = path.resolve(PACKAGE_ROOT, "../..");
const MAIN_DIRECTORY = "curupira";
const MAIN_PACKAGE_NAME = "@caipora-labs/curupira";

/**
 * Assemble the single npm package from Cargo binaries or maturin wheels.
 *
 * The published tarballs contain the already-built Rust executable. Nothing here
 * compiles Rust or downloads a binary.
 */
function main(argv) {
  const { command, options } = parseArgs(argv);
  try {
    if (command === "binary") stageBinary(options);
    else if (command === "wheel") stageFromWheel(options);
    else if (command === "main") stageMain(options);
    else if (command === "verify") verifyAll(options.dir, options.version);
    else if (command === "verify-one") verifyOne(options.dir, options.target, options.version);
    else if (command === "verify-tarballs") verifyTarballs(options.dir, options.version, options.count);
    else {
      throw new Error(
        "Usage: assemble.js <binary|wheel|main|verify|verify-one|verify-tarballs> [--bin PATH] [--wheel PATH] [--target KEY] [--version VER] [--out DIR] [--dir DIR] [--count N]",
      );
    }
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exit(1);
  }
}

/**
 * @param {string[]} argv
 * @returns {{ command: string | undefined, options: Record<string, string> }}
 */
function parseArgs(argv) {
  const [command, ...rest] = argv;
  /** @type {Record<string, string>} */
  const options = {};
  for (let index = 0; index < rest.length; index += 1) {
    const item = rest[index];
    if (!item.startsWith("--")) {
      throw new Error(`Unexpected argument ${item}`);
    }
    const key = item.slice(2);
    const value = rest[index + 1];
    if (value === undefined || value.startsWith("--")) {
      throw new Error(`Missing value for --${key}`);
    }
    options[key] = value;
    index += 1;
  }
  return { command, options };
}

/**
 * @param {Record<string, string>} options
 */
function stageBinary(options) {
  const target = requireTarget(options.target);
  const version = requireVersion(options.version);
  const outDir = requirePath(options.out, "--out");
  const bin = requirePath(options.bin, "--bin");
  assertNativeBinary(bin);
  writePlatformBinary(target, bin, outDir);
}

/**
 * @param {Record<string, string>} options
 */
function stageFromWheel(options) {
  const target = requireTarget(options.target);
  const version = requireVersion(options.version);
  const outDir = requirePath(options.out, "--out");
  const wheel = requirePath(options.wheel, "--wheel");
  const extracted = path.join(outDir, ".wheel", target.key);
  fs.rmSync(extracted, { recursive: true, force: true });
  unzip(wheel, extracted);
  const bin = findNativeBinary(extracted, binaryFileName(target.os));
  writePlatformBinary(target, bin, outDir);
  fs.rmSync(path.join(outDir, ".wheel"), { recursive: true, force: true });
}

/**
 * @param {Record<string, string>} options
 */
function stageMain(options) {
  const version = requireVersion(options.version);
  const outDir = requirePath(options.out, "--out");
  const destination = path.join(outDir, MAIN_DIRECTORY);
  fs.rmSync(destination, { recursive: true, force: true });
  fs.mkdirSync(destination, { recursive: true });
  const manifest = JSON.parse(fs.readFileSync(path.join(PACKAGE_ROOT, "package.json"), "utf8"));
  manifest.version = version;
  delete manifest.scripts;
  delete manifest.optionalDependencies;
  fs.writeFileSync(path.join(destination, "package.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  copyTree(path.join(PACKAGE_ROOT, "bin"), path.join(destination, "bin"));
  for (const target of TARGETS) {
    const source = binaryPath(outDir, target, "staging");
    assertNativeBinary(source);
    const binary = binaryPath(destination, target, "package");
    fs.mkdirSync(path.dirname(binary), { recursive: true });
    fs.copyFileSync(source, binary);
    fs.chmodSync(binary, 0o755);
  }
  fs.rmSync(path.join(outDir, "binaries"), { recursive: true, force: true });
  const libDir = path.join(destination, "lib");
  fs.mkdirSync(libDir, { recursive: true });
  for (const file of ["launch.js", "targets.js"]) {
    fs.copyFileSync(path.join(PACKAGE_ROOT, "lib", file), path.join(libDir, file));
  }
  fs.copyFileSync(path.join(PACKAGE_ROOT, "README.md"), path.join(destination, "README.md"));
  fs.copyFileSync(licensePath(), path.join(destination, "LICENSE"));
  for (const file of ["bin/curupira.js", "bin/curu.js"]) {
    fs.chmodSync(path.join(destination, file), 0o755);
  }
}

/**
 * @param {(typeof TARGETS)[number]} target
 * @param {string} bin
 * @param {string} outDir
 */
function writePlatformBinary(target, bin, outDir) {
  const binary = binaryPath(outDir, target, "staging");
  fs.mkdirSync(path.dirname(binary), { recursive: true });
  fs.copyFileSync(bin, binary);
  fs.chmodSync(binary, 0o755);
}

/**
 * @param {string} root
 * @param {string} version
 */
function verifyAll(root, version) {
  const expected = requireVersion(version);
  const stage = requirePath(root, "--dir");
  verifySinglePackage(path.join(stage, MAIN_DIRECTORY), expected);
}

/**
 * @param {string} root
 * @param {string | undefined} key
 * @param {string | undefined} version
 */
function verifyOne(root, key, version) {
  const target = requireTarget(key);
  const binary = binaryPath(requirePath(root, "--dir"), target, "staging");
  requireVersion(version);
  assertNativeBinary(binary);
}

/**
 * Check the single npm pack tarball contains the expected manifest and all native binaries.
 *
 * @param {string | undefined} dir
 * @param {string | undefined} version
 * @param {string | undefined} count
 */
function verifyTarballs(dir, version, count) {
  const expected = requireVersion(version);
  const root = requirePath(dir, "--dir");
  const tarballs = listTarballs(root);
  const expectedCount = count === undefined ? 1 : Number(count);
  if (!Number.isInteger(expectedCount) || tarballs.length !== expectedCount) {
    throw new Error(
      `Expected ${expectedCount} npm tarballs in ${root}, found ${tarballs.map((file) => path.basename(file)).join(", ") || "none"}`,
    );
  }
  for (const tarball of tarballs) {
    const extracted = fs.mkdtempSync(path.join(os.tmpdir(), "curupira-npm-tgz-"));
    try {
      execFileSync("tar", ["-xzf", tarball, "-C", extracted], { stdio: "inherit" });
      const packageDir = path.join(extracted, "package");
      verifySinglePackage(packageDir, expected, path.basename(tarball));
    } finally {
      fs.rmSync(extracted, { recursive: true, force: true });
    }
  }
}

/**
 * @param {string} root
 * @returns {string[]}
 */
function listTarballs(root) {
  /** @type {string[]} */
  const found = [];
  walk(root, (file) => {
    if (file.endsWith(".tgz")) found.push(file);
  });
  return found.sort();
}

/**
 * @param {string} directory
 * @param {string} version
 * @param {string} [label]
 */
function verifySinglePackage(directory, version, label = MAIN_DIRECTORY) {
  const manifest = readManifest(path.join(directory, "package.json"));
  assertVersion(manifest, version, label);
  if (manifest.name !== MAIN_PACKAGE_NAME) {
    throw new Error(`${label} is named ${manifest.name}, expected ${MAIN_PACKAGE_NAME}`);
  }
  if (manifest.optionalDependencies && Object.keys(manifest.optionalDependencies).length > 0) {
    throw new Error(`${label} must bundle its platform binaries instead of using optional dependencies`);
  }
  for (const target of TARGETS) {
    const binary = binaryPath(directory, target, "package");
    assertNativeBinary(binary);
    if ((fs.statSync(binary).mode & 0o111) === 0) {
      throw new Error(`${binary} is not executable`);
    }
  }
  const embedded = fs.readdirSync(path.join(directory, "bin", "platforms")).sort();
  const expected = TARGETS.map((target) => target.key).sort();
  if (JSON.stringify(embedded) !== JSON.stringify(expected)) {
    throw new Error(`${label} has unexpected platform binaries: ${embedded.join(", ")}`);
  }
  if (!fs.existsSync(path.join(directory, "LICENSE"))) {
    throw new Error(`${label} is missing LICENSE`);
  }
}

/**
 * @param {string} root
 * @param {(typeof TARGETS)[number]} target
 * @param {"staging" | "package"} layout
 * @returns {string}
 */
function binaryPath(root, target, layout) {
  const base = layout === "staging" ? path.join(root, "binaries") : path.join(root, "bin", "platforms");
  return path.join(base, target.key, binaryFileName(target.os));
}

/**
 * @param {string} root
 * @param {string} expectedName `curupira` or `curupira.exe`
 * @returns {string}
 */
function findNativeBinary(root, expectedName) {
  /** @type {string[]} */
  const found = [];
  walk(root, (file) => {
    const base = path.basename(file);
    if (base === "curupira" || base === "curupira.exe") found.push(file);
  });
  const natives = found.filter((file) => isNativeBinary(file) && path.basename(file) === expectedName);
  if (natives.length !== 1) {
    throw new Error(
      `Expected one native ${expectedName}, found ${found.map((file) => path.basename(file)).join(", ") || "none"}`,
    );
  }
  return natives[0];
}

/**
 * @param {string} file
 */
function assertNativeBinary(file) {
  if (!isNativeBinary(file)) {
    throw new Error(`${file} is not an ELF, Mach-O, or PE executable`);
  }
}

/**
 * @param {string} file
 * @returns {boolean}
 */
function isNativeBinary(file) {
  let fd;
  try {
    fd = fs.openSync(file, "r");
  } catch {
    return false;
  }
  const header = Buffer.alloc(4);
  try {
    const read = fs.readSync(fd, header, 0, 4, 0);
    if (read < 2) return false;
  } finally {
    fs.closeSync(fd);
  }
  const elf = header[0] === 0x7f && header[1] === 0x45 && header[2] === 0x4c && header[3] === 0x46;
  const pe = header[0] === 0x4d && header[1] === 0x5a;
  const macho =
    (header[0] === 0xfe && header[1] === 0xed && header[2] === 0xfa && (header[3] === 0xcf || header[3] === 0xce)) ||
    (header[0] === 0xcf && header[1] === 0xfa && header[2] === 0xed && header[3] === 0xfe) ||
    (header[0] === 0xce && header[1] === 0xfa && header[2] === 0xed && header[3] === 0xfe) ||
    (header[0] === 0xca && header[1] === 0xfe && header[2] === 0xba && header[3] === 0xbe);
  return elf || pe || macho;
}

/**
 * @param {string} directory
 * @param {(file: string) => void} visit
 */
function walk(directory, visit) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const full = path.join(directory, entry.name);
    if (entry.isDirectory()) walk(full, visit);
    else if (entry.isFile()) visit(full);
  }
}

/**
 * @param {string} from
 * @param {string} to
 */
function copyTree(from, to) {
  fs.cpSync(from, to, { recursive: true });
}

/**
 * @returns {string}
 */
function licensePath() {
  return path.join(REPO_ROOT, "LICENSE");
}

/**
 * @param {string | undefined} key
 * @returns {(typeof TARGETS)[number]}
 */
function requireTarget(key) {
  const found = TARGETS.find((item) => item.key === key);
  if (found === undefined) {
    throw new Error(`Unknown target ${key}. Expected one of ${TARGETS.map((item) => item.key).join(", ")}`);
  }
  return found;
}

/**
 * @param {string | undefined} version
 * @returns {string}
 */
function requireVersion(version) {
  if (version === undefined || version.length === 0) throw new Error("Missing --version");
  return version;
}

/**
 * @param {string | undefined} value
 * @param {string} flag
 * @returns {string}
 */
function requirePath(value, flag) {
  if (value === undefined || value.length === 0) throw new Error(`Missing ${flag}`);
  return value;
}

/**
 * @param {string} file
 * @returns {any}
 */
function readManifest(file) {
  return JSON.parse(fs.readFileSync(file, "utf8"));
}

/**
 * @param {{ version?: string, name?: string }} manifest
 * @param {string} version
 * @param {string} label
 */
function assertVersion(manifest, version, label) {
  if (manifest.version !== version) {
    throw new Error(`${label} is version ${manifest.version}, expected ${version}`);
  }
}

module.exports = {
  findNativeBinary,
  isNativeBinary,
  main,
  stageBinary,
  stageFromWheel,
  stageMain,
  verifyAll,
  verifyOne,
  verifyTarballs,
};

if (require.main === module) {
  main(process.argv.slice(2));
}
