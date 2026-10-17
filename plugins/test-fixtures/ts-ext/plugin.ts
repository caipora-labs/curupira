#!/usr/bin/env node
/**
 * TypeScript test extension. Run with: npx --yes tsx plugin.ts
 * or compile/run under Node after transpile. The published pattern is
 * a package "bin" pointing at a JS entry compiled from TypeScript.
 */
const PROTOCOL = 1;

function writeFrame(obj: unknown): void {
  const body = Buffer.from(JSON.stringify(obj), "utf8");
  const header = Buffer.from(body.length.toString(16).padStart(8, "0"), "ascii");
  process.stdout.write(header);
  process.stdout.write(body);
}

async function* frames(stream: NodeJS.ReadStream): AsyncGenerator<any> {
  let buf = Buffer.alloc(0);
  for await (const chunk of stream) {
    buf = Buffer.concat([buf, chunk as Buffer]);
    while (buf.length >= 8) {
      const len = parseInt(buf.subarray(0, 8).toString("ascii"), 16);
      if (buf.length < 8 + len) break;
      const body = buf.subarray(8, 8 + len);
      buf = buf.subarray(8 + len);
      yield JSON.parse(body.toString("utf8"));
    }
  }
}

(async () => {
  for await (const req of frames(process.stdin)) {
    const id = req.id;
    if (req.method === "initialize") {
      writeFrame({
        jsonrpc: "2.0",
        id,
        result: {
          protocol_version: PROTOCOL,
          server_info: { name: "ts-test-ext", version: "0.0.1" },
        },
      });
    } else if (req.method === "describe") {
      writeFrame({
        jsonrpc: "2.0",
        id,
        result: {
          triggers: [{ trigger_type: "ts-test", prompt_fields: ["id"] }],
          agents: [],
        },
      });
    } else if (req.method === "trigger/poll") {
      writeFrame({ jsonrpc: "2.0", id, result: { tasks: [] } });
    } else if (req.method === "shutdown") {
      writeFrame({ jsonrpc: "2.0", id, result: {} });
      return;
    } else if (req.method === "trigger/validate") {
      writeFrame({
        jsonrpc: "2.0",
        id,
        result: { ok: true, configuration: (req.params || {}).configuration },
      });
    } else {
      writeFrame({
        jsonrpc: "2.0",
        id,
        error: { code: -32601, message: `missing ${req.method}` },
      });
    }
  }
})();
