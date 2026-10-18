import { writeSync } from "node:fs";

export const DEFAULT_MAX_FRAME_BYTES = 16 * 1024 * 1024;

/** Write one length-prefixed frame to a binary writable (typically stdout). */
export function writeFrame(
  writer: NodeJS.WritableStream,
  payload: Uint8Array | Buffer,
): void {
  if (payload.length > 0xffffffff) {
    throw new Error("frame too large");
  }
  const header = Buffer.from(payload.length.toString(16).padStart(8, "0"), "ascii");
  writer.write(header);
  writer.write(payload);
}

/** Write a diagnostic line to stderr (never stdout). */
export function log(message: string): void {
  writeSync(2, `${message}\n`);
}

/**
 * Async iterator of frame bodies from a readable stream (typically stdin).
 */
export async function* readFrames(
  stream: AsyncIterable<Buffer | Uint8Array>,
  maxBytes: number = DEFAULT_MAX_FRAME_BYTES,
): AsyncGenerator<Buffer> {
  let buf = Buffer.alloc(0);
  for await (const chunk of stream) {
    buf = Buffer.concat([buf, Buffer.from(chunk)]);
    while (buf.length >= 8) {
      const length = Number.parseInt(buf.subarray(0, 8).toString("ascii"), 16);
      if (Number.isNaN(length)) {
        throw new Error("invalid frame header");
      }
      if (length > maxBytes) {
        throw new Error(`frame length ${length} exceeds limit ${maxBytes}`);
      }
      if (buf.length < 8 + length) {
        break;
      }
      const body = buf.subarray(8, 8 + length);
      buf = buf.subarray(8 + length);
      yield Buffer.from(body);
    }
  }
}
