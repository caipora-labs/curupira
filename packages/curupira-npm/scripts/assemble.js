#!/usr/bin/env node
"use strict";

const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const { TARGETS, binaryFileName, packageDirectory } = require("../lib/targets.js");
const { unzip } = require("./unzip.js");

const PACKAGE_ROOT = path.resolve(__dirname, "..");
const REPO_ROOT = path.resolve(PACKAGE_ROOT, "../..");
const MAIN_DIRECTORY = "curupira";

/**
 * Stage npm packages from a Cargo binary or a maturin wheel.
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
  writePlatformPackage(target, version, bin, outDir);
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
  writePlatformPackage(target, version, bin, outDir);
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
  manifest.optionalDependencies = Object.fromEntries(
    TARGETS.map((target) => [target.packageName, version]),
  );
  fs.writeFileSync(path.join(destination, "package.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  copyTree(path.join(PACKAGE_ROOT, "bin"), path.join(destination, "bin"));
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
 * @param {string} version
 * @param {string} bin
 * @param {string} outDir
 */
function writePlatformPackage(target, version, bin, outDir) {
  const destination = path.join(outDir, packageDirectory(target.packageName));
  fs.rmSync(destination, { recursive: true, force: true });
  const binDir = path.join(destination, "bin");
  fs.mkdirSync(binDir, { recursive: true });
  const binary = path.join(binDir, binaryFileName(target.os));
  fs.copyFileSync(bin, binary);
  fs.chmodSync(binary, 0o755);
  fs.writeFileSync(path.join(destination, "package.json"), `${JSON.stringify(platformManifest(target, version), null, 2)}\n`);
  fs.writeFileSync(path.join(destination, "README.md"), platformReadme(target));
  fs.copyFileSync(licensePath(), path.join(destination, "LICENSE"));
}

/**
 * @param {(typeof TARGETS)[number]} target
 * @param {string} version
 * @returns {Record<string, unknown>}
 */
function platformManifest(target, version) {
  /** @type {Record<string, unknown>} */
  const manifest = {
    name: target.packageName,
    version,
    description: target.description,
    license: "MIT",
    repository: repository(),
    homepage: "https://github.com/caipora-labs/curupira/tree/main/packages/curupira-npm",
    bugs: { url: "https://github.com/caipora-labs/curupira/issues" },
    os: [target.os],
    cpu: [target.cpu],
    files: ["bin", "README.md", "LICENSE"],
    publishConfig: { access: "public" },
  };
  if (target.libc !== null) manifest.libc = [target.libc];
  return manifest;
}

/**
 * @returns {Record<string, unknown>}
 */
function repository() {
  return {
    type: "git",
    url: "git+https://github.com/caipora-labs/curupira.git",
    directory: "packages/curupira-npm",
  };
}

/**
 * @param {(typeof TARGETS)[number]} target
 * @returns {string}
 */
function platformReadme(target) {
  return (
    `# ${target.packageName}\n\n` +
    `${target.description}\n\n` +
    "This package is an optional dependency of [`@caipora/curupira`](https://www.npmjs.com/package/@caipora/curupira). " +
    "Install the CLI with `npm install -g @caipora/curupira`. Do not depend on this package directly.\n"
  );
}

/**
 * @param {string} root
 * @param {string} version
 */
function verifyAll(root, version) {
  const expected = requireVersion(version);
  const stage = requirePath(root, "--dir");
  const main = readManifest(path.join(stage, MAIN_DIRECTORY, "package.json"));
  assertVersion(main, expected, MAIN_DIRECTORY);
  if (main.name !== "@caipora/curupira") {
    throw new Error(`Main package name is ${main.name}`);
  }
  const dependencies = main.optionalDependencies ?? {};
  for (const target of TARGETS) {
    if (dependencies[target.packageName] !== expected) {
      throw new Error(`${target.packageName} is ${dependencies[target.packageName]}, expected ${expected}`);
    }
    verifyPlatform(stage, target, expected);
  }
  const extra = Object.keys(dependencies).filter(
    (name) => !TARGETS.some((target) => target.packageName === name),
  );
  if (extra.length > 0) {
    throw new Error(`Unexpected optional dependencies: ${extra.join(", ")}`);
  }
}

/**
 * @param {string} root
 * @param {string | undefined} key
 * @param {string | undefined} version
 */
function verifyOne(root, key, version) {
  const target = requireTarget(key);
  verifyPlatform(requirePath(root, "--dir"), target, requireVersion(version));
}

/**
 * Check npm pack tarballs. Each archive must contain `package/package.json` at `version`.
 *
 * @param {string | undefined} dir
 * @param {string | undefined} version
 * @param {string | undefined} count
 */
function verifyTarballs(dir, version, count) {
  const expected = requireVersion(version);
  const root = requirePath(dir, "--dir");
  const tarballs = listTarballs(root);
  const expectedCount = count === undefined ? TARGETS.length + 1 : Number(count);
  if (!Number.isInteger(expectedCount) || tarballs.length !== expectedCount) {
    throw new Error(
      `Expected ${expectedCount} npm tarballs in ${root}, found ${tarballs.map((file) => path.basename(file)).join(", ") || "none"}`,
    );
  }
  for (const tarball of tarballs) {
    const extracted = fs.mkdtempSync(path.join(os.tmpdir(), "curupira-npm-tgz-"));
    try {
      execFileSync("tar", ["-xzf", tarball, "-C", extracted], { stdio: "inherit" });
      const manifestPath = path.join(extracted, "package", "package.json");
      if (!fs.existsSync(manifestPath)) {
        throw new Error(`Missing package/package.json in ${tarball}`);
      }
      const manifest = readManifest(manifestPath);
      assertVersion(manifest, expected, path.basename(tarball));
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
 * @param {string} stage
 * @param {(typeof TARGETS)[number]} target
 * @param {string} version
 */
function verifyPlatform(stage, target, version) {
  const directory = path.join(stage, packageDirectory(target.packageName));
  const manifest = readManifest(path.join(directory, "package.json"));
  assertVersion(manifest, version, target.packageName);
  if (manifest.name !== target.packageName) {
    throw new Error(`${directory} is named ${manifest.name}`);
  }
  if (!Array.isArray(manifest.os) || manifest.os[0] !== target.os) {
    throw new Error(`${target.packageName} os is ${JSON.stringify(manifest.os)}`);
  }
  if (!Array.isArray(manifest.cpu) || manifest.cpu[0] !== target.cpu) {
    throw new Error(`${target.packageName} cpu is ${JSON.stringify(manifest.cpu)}`);
  }
  const libc = manifest.libc ?? null;
  const expectedLibc = target.libc === null ? null : [target.libc];
  if (JSON.stringify(libc) !== JSON.stringify(expectedLibc)) {
    throw new Error(`${target.packageName} libc is ${JSON.stringify(libc)}`);
  }
  if (manifest.bin !== undefined) {
    throw new Error(`${target.packageName} must not publish its own bin entries`);
  }
  const binary = path.join(directory, "bin", binaryFileName(target.os));
  assertNativeBinary(binary);
  if (fs.existsSync(path.join(directory, "LICENSE")) === false) {
    throw new Error(`${target.packageName} is missing LICENSE`);
  }
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
