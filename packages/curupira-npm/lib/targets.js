"use strict";

/**
 * Official npm platform packages for the Curupira CLI.
 *
 * Keys match `npm_target` in `.github/workflows/publish.yml`. npm installs only the
 * optional dependency whose `os`, `cpu`, and `libc` match the current machine.
 */

const TARGETS = Object.freeze([
  target("linux-x64", "linux", "x64", "glibc", "Linux x64 (glibc)"),
  target("linux-arm64", "linux", "arm64", "glibc", "Linux ARM64 (glibc)"),
  target("linux-x64-musl", "linux", "x64", "musl", "Linux x64 (musl)"),
  target("linux-arm64-musl", "linux", "arm64", "musl", "Linux ARM64 (musl)"),
  target("darwin-x64", "darwin", "x64", null, "macOS x64"),
  target("darwin-arm64", "darwin", "arm64", null, "macOS ARM64"),
  target("win32-x64", "win32", "x64", null, "Windows x64"),
  target("win32-arm64", "win32", "arm64", null, "Windows ARM64"),
]);

/**
 * @param {string} key
 * @param {string} osName
 * @param {string} cpu
 * @param {string | null} libc
 * @param {string} label
 */
function target(key, osName, cpu, libc, label) {
  return Object.freeze({
    key,
    os: osName,
    cpu,
    libc,
    label,
    packageName: `@caipora-labs/curupira-${key}`,
    description: `Prebuilt Curupira CLI for ${label}.`,
  });
}

/**
 * @param {string} platform Node `process.platform`
 * @param {string} arch Node `process.arch`
 * @param {string | null} libc `glibc`, `musl`, or null off Linux
 * @returns {(typeof TARGETS)[number] | null}
 */
function selectTarget(platform, arch, libc) {
  if (platform === "linux") {
    const suffix = libc === "musl" ? "-musl" : "";
    return TARGETS.find((item) => item.key === `linux-${arch}${suffix}`) ?? null;
  }
  if (platform === "darwin" || platform === "win32") {
    return TARGETS.find((item) => item.key === `${platform}-${arch}`) ?? null;
  }
  return null;
}

/**
 * @param {string} osName
 * @returns {string}
 */
function binaryFileName(osName) {
  return osName === "win32" ? "curupira.exe" : "curupira";
}

/**
 * @param {string} packageName Scoped package name.
 * @returns {string}
 */
function packageDirectory(packageName) {
  const slash = packageName.lastIndexOf("/");
  return slash === -1 ? packageName : packageName.slice(slash + 1);
}

/**
 * @returns {string[]}
 */
function supportedKeys() {
  return TARGETS.map((item) => item.key);
}

module.exports = {
  TARGETS,
  binaryFileName,
  packageDirectory,
  selectTarget,
  supportedKeys,
};
