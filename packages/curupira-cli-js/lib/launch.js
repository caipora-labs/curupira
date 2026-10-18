"use strict";

const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const { binaryFileName, selectTarget, supportedKeys } = require("./targets.js");

const PACKAGE_ROOT = path.resolve(__dirname, "..");
const MUSL_LOADERS = ["/lib/ld-musl-x86_64.so.1", "/lib/ld-musl-aarch64.so.1"];
const UNIX_SIGNALS = ["SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT"];
const WINDOWS_SIGNALS = ["SIGINT", "SIGTERM", "SIGBREAK"];
const SIGNAL_NUMBERS = {
  SIGHUP: 1,
  SIGINT: 2,
  SIGQUIT: 3,
  SIGTERM: 15,
  SIGBREAK: 21,
};

/**
 * Detect the Linux C library. Non-Linux platforms return null.
 *
 * @param {string} platform
 * @param {() => { header?: { glibcVersionRuntime?: string }, sharedObjects?: string[] } | null} [report]
 * @param {(file: string) => boolean} [exists]
 * @returns {"glibc" | "musl" | null}
 */
function detectLibc(platform, report = readProcessReport, exists = fs.existsSync) {
  if (platform !== "linux") return null;
  let data = null;
  try {
    data = report();
  } catch {
    data = null;
  }
  const shared = Array.isArray(data?.sharedObjects) ? data.sharedObjects : [];
  if (
    shared.some(
      (item) =>
        typeof item === "string" && (item.includes("ld-musl-") || item.includes("libc.musl")),
    )
  ) {
    return "musl";
  }
  if (data?.header?.glibcVersionRuntime) return "glibc";
  if (MUSL_LOADERS.some((loader) => exists(loader))) return "musl";
  return "glibc";
}

/**
 * @returns {{ header?: { glibcVersionRuntime?: string }, sharedObjects?: string[] } | null}
 */
function readProcessReport() {
  if (typeof process.report?.getReport !== "function") return null;
  return process.report.getReport();
}

/**
 * Resolve the native binary for this process without spawning it.
 *
 * @param {{
 *   args?: string[],
 *   argv0?: string,
 *   packageRoot?: string,
 *   platform?: string,
 *   arch?: string,
 *   libc?: string | null,
 * }} options
 * @returns {{ error: string } | { bin: string, args: string[], spawnOptions: object }}
 */
function prepare(options = {}) {
  const platform = options.platform ?? process.platform;
  const arch = options.arch ?? process.arch;
  const libc = options.libc === undefined ? detectLibc(platform) : options.libc;
  const packageRoot = options.packageRoot ?? PACKAGE_ROOT;
  const args = options.args ?? [];
  const target = selectTarget(platform, arch, libc);
  if (target === null) {
    return { error: unsupportedPlatformMessage(platform, arch) };
  }
  const bin = path.join(packageRoot, "bin", "platforms", target.key, binaryFileName(platform));
  if (!fs.existsSync(bin)) {
    return { error: missingBinaryMessage(target.key, bin) };
  }
  return {
    bin,
    args,
    spawnOptions: {
      stdio: "inherit",
      argv0: options.argv0,
      shell: false,
    },
  };
}

/**
 * Replace the current Node process with the native CLI.
 *
 * @param {string} argv0 `curupira` or `curu`. The Rust binary prints this name for `--version`.
 */
function run(argv0) {
  const prepared = prepare({
    args: process.argv.slice(2),
    argv0,
  });
  if ("error" in prepared) {
    process.stderr.write(`${prepared.error}\n`);
    process.exit(1);
  }
  const child = spawn(prepared.bin, prepared.args, prepared.spawnOptions);
  bindLifecycle(child, prepared.bin, process.platform);
}

/**
 * Forward termination signals to the Rust process and exit with its status.
 *
 * Supervisors and the npm shim often signal only this Node process. The child stays
 * in the same process group and keeps the caller's stdin, stdout, stderr, cwd, and
 * environment (`stdio: "inherit"`, no `cwd` or `env` override).
 *
 * @param {import("node:child_process").ChildProcess} child
 * @param {string} binPath
 * @param {string} platform
 */
function bindLifecycle(child, binPath, platform) {
  let settled = false;
  const finish = (code) => {
    if (settled) return;
    settled = true;
    process.exit(code);
  };
  let forwarding = false;
  for (const signal of platform === "win32" ? WINDOWS_SIGNALS : UNIX_SIGNALS) {
    process.on(signal, () => {
      if (forwarding || settled) return;
      if (child.exitCode !== null || child.signalCode !== null) return;
      forwarding = true;
      child.kill(signal);
      forwarding = false;
    });
  }
  child.on("error", (error) => {
    process.stderr.write(`${spawnErrorMessage(binPath, error)}\n`);
    finish(1);
  });
  child.on("exit", (code, signal) => {
    if (settled) return;
    if (code === null && signal) {
      settled = true;
      process.removeAllListeners(signal);
      try {
        process.kill(process.pid, signal);
      } catch {
        // Fall back when the host cannot re-raise the signal.
      }
      process.exit(exitStatusForSignal(signal));
      return;
    }
    finish(code === null ? 1 : code);
  });
}

/**
 * @param {string} signal
 * @returns {number}
 */
function exitStatusForSignal(signal) {
  const number = SIGNAL_NUMBERS[signal];
  return number === undefined ? 1 : 128 + number;
}

/**
 * @param {string} platform
 * @param {string} arch
 * @returns {string}
 */
function unsupportedPlatformMessage(platform, arch) {
  return (
    `Curupira has no npm binary for ${platform} ${arch}. ` +
    `Supported platforms: ${supportedKeys().join(", ")}.`
  );
}

/**
 * @param {string} target
 * @returns {string}
 */
function missingBinaryMessage(target, binPath) {
  return (
    `Curupira binary for ${target} is missing from ${binPath}. ` +
    "Reinstall with `npm install -g @caipora-labs/curupira`."
  );
}

/**
 * @param {string} binPath
 * @param {Error} error
 * @returns {string}
 */
function spawnErrorMessage(binPath, error) {
  return `Failed to start Curupira binary at ${binPath}: ${error.message}`;
}

module.exports = {
  bindLifecycle,
  detectLibc,
  exitStatusForSignal,
  prepare,
  run,
};
