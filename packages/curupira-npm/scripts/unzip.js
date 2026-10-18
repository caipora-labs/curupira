"use strict";

const fs = require("node:fs");
const path = require("node:path");
const zlib = require("node:zlib");

/**
 * Extract a ZIP archive (stored or deflated entries).
 *
 * Wheels are ZIP files. The extractor rejects absolute paths and `..` segments so a
 * hostile archive cannot write outside `destDir`.
 *
 * @param {string} zipPath
 * @param {string} destDir
 */
function unzip(zipPath, destDir) {
  const data = fs.readFileSync(zipPath);
  const eocd = findEndOfCentralDirectory(data);
  fs.mkdirSync(destDir, { recursive: true });
  let offset = eocd.cdOffset;
  for (let index = 0; index < eocd.entries; index += 1) {
    offset = extractEntry(data, offset, destDir);
  }
}

/**
 * @param {Buffer} data
 * @returns {{ entries: number, cdOffset: number }}
 */
function findEndOfCentralDirectory(data) {
  const signature = 0x06054b50;
  const lower = Math.max(0, data.length - 22 - 65535);
  for (let offset = data.length - 22; offset >= lower; offset -= 1) {
    if (data.readUInt32LE(offset) !== signature) continue;
    const commentLength = data.readUInt16LE(offset + 20);
    if (offset + 22 + commentLength !== data.length) continue;
    const entries = data.readUInt16LE(offset + 10);
    const cdOffset = data.readUInt32LE(offset + 16);
    if (entries === 0xffff || cdOffset === 0xffffffff) {
      throw new Error("ZIP64 archives are not supported");
    }
    return { entries, cdOffset };
  }
  throw new Error("ZIP end of central directory not found");
}

/**
 * @param {Buffer} data
 * @param {number} offset
 * @param {string} destDir
 * @returns {number} Offset of the next central-directory entry.
 */
function extractEntry(data, offset, destDir) {
  if (data.readUInt32LE(offset) !== 0x02014b50) {
    throw new Error("Invalid ZIP central directory");
  }
  const method = data.readUInt16LE(offset + 10);
  const compressedSize = data.readUInt32LE(offset + 20);
  const uncompressedSize = data.readUInt32LE(offset + 24);
  const nameLength = data.readUInt16LE(offset + 28);
  const extraLength = data.readUInt16LE(offset + 30);
  const commentLength = data.readUInt16LE(offset + 32);
  const localOffset = data.readUInt32LE(offset + 42);
  const name = data.slice(offset + 46, offset + 46 + nameLength).toString("utf8");
  const next = offset + 46 + nameLength + extraLength + commentLength;
  if (name.endsWith("/")) return next;
  const output = safeJoin(destDir, name);
  if (data.readUInt32LE(localOffset) !== 0x04034b50) {
    throw new Error(`Invalid ZIP local header for ${name}`);
  }
  const localNameLength = data.readUInt16LE(localOffset + 26);
  const localExtraLength = data.readUInt16LE(localOffset + 28);
  const dataStart = localOffset + 30 + localNameLength + localExtraLength;
  const compressed = data.subarray(dataStart, dataStart + compressedSize);
  const content = inflate(method, compressed, name);
  if (uncompressedSize !== 0xffffffff && content.length !== uncompressedSize) {
    throw new Error(`Uncompressed size mismatch for ${name}`);
  }
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, content);
  return next;
}

/**
 * @param {number} method
 * @param {Buffer} compressed
 * @param {string} name
 * @returns {Buffer}
 */
function inflate(method, compressed, name) {
  if (method === 0) return Buffer.from(compressed);
  if (method === 8) return zlib.inflateRawSync(compressed);
  throw new Error(`Unsupported ZIP method ${method} for ${name}`);
}

/**
 * @param {string} destDir
 * @param {string} name
 * @returns {string}
 */
function safeJoin(destDir, name) {
  if (name.includes("\\") || path.isAbsolute(name)) {
    throw new Error(`Unsafe ZIP path ${name}`);
  }
  const output = path.resolve(destDir, ...name.split("/"));
  const relative = path.relative(destDir, output);
  if (relative.startsWith("..") || path.isAbsolute(relative)) {
    throw new Error(`Unsafe ZIP path ${name}`);
  }
  return output;
}

module.exports = { unzip };
