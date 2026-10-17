#!/usr/bin/env node
"use strict";

const PROTOCOL = 1;

function writeFrame(obj) {
  const body = Buffer.from(JSON.stringify(obj), "utf8");
  const header = Buffer.from(body.length.toString(16).padStart(8, "0"), "ascii");
  process.stdout.write(header);
  process.stdout.write(body);
}

async function* frames(stream) {
  let buf = Buffer.alloc(0);
  for await (const chunk of stream) {
    buf = Buffer.concat([buf, chunk]);
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
    let result;
    if (req.method === "initialize") {
      result = {
        protocol_version: PROTOCOL,
        server_info: { name: "node-test-ext", version: "0.0.1" },
      };
    } else if (req.method === "describe") {
      result = {
        triggers: [{ trigger_type: "node-test", prompt_fields: ["id"] }],
        agents: [],
      };
    } else if (req.method === "trigger/validate") {
      result = { ok: true, configuration: (req.params || {}).configuration };
    } else if (req.method === "trigger/poll") {
      result = { task: null };
    } else if (req.method === "shutdown") {
      writeFrame({ jsonrpc: "2.0", id, result: {} });
      return;
    } else {
      writeFrame({
        jsonrpc: "2.0",
        id,
        error: { code: -32601, message: `missing ${req.method}` },
      });
      continue;
    }
    writeFrame({ jsonrpc: "2.0", id, result });
  }
})();
