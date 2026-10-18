import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, it } from "node:test";

import { writeFrame } from "../dist/framing.js";
import { PROTOCOL_VERSION } from "../dist/types.js";

const here = dirname(fileURLToPath(import.meta.url));
// Compiled tests live in dist/test/; fixtures stay under test/fixtures/.
const packageRoot = join(here, "..");
const fixture = join(packageRoot, "test/fixtures/example-jsdoc.js");

describe("JSDoc JavaScript example", () => {
  it("loads and serves the protocol", async () => {
    const child = spawn(process.execPath, [fixture], {
      stdio: ["pipe", "pipe", "inherit"],
      cwd: packageRoot,
    });
    assert.ok(child.stdin && child.stdout);

    let buf = Buffer.alloc(0);
    const read = (): Promise<unknown> =>
      new Promise((resolve, reject) => {
        const tryParse = () => {
          if (buf.length < 8) {
            return false;
          }
          const len = Number.parseInt(buf.subarray(0, 8).toString("ascii"), 16);
          if (buf.length < 8 + len) {
            return false;
          }
          const body = buf.subarray(8, 8 + len);
          buf = buf.subarray(8 + len);
          resolve(JSON.parse(body.toString("utf8")));
          return true;
        };
        const onData = (chunk: Buffer) => {
          buf = Buffer.concat([buf, chunk]);
          if (tryParse()) {
            child.stdout?.off("data", onData);
          }
        };
        child.stdout?.on("data", onData);
        child.on("error", reject);
        child.on("exit", (code) => {
          if (!tryParse()) {
            reject(new Error(`plugin exited early with code ${code}`));
          }
        });
      });

    const send = (obj: unknown) => {
      writeFrame(child.stdin!, Buffer.from(JSON.stringify(obj), "utf8"));
    };

    try {
      send({
        jsonrpc: "2.0",
        id: 1,
        method: "initialize",
        params: {
          protocol_version: PROTOCOL_VERSION,
          client_info: { name: "t", version: "0" },
        },
      });
      const init = (await read()) as { result: { protocol_version: number } };
      assert.equal(init.result.protocol_version, 2);

      send({ jsonrpc: "2.0", id: 2, method: "describe", params: {} });
      const described = (await read()) as {
        result: { triggers: { trigger_type: string }[] };
      };
      assert.equal(described.result.triggers[0]?.trigger_type, "github-issue");

      send({ jsonrpc: "2.0", id: 3, method: "shutdown", params: {} });
      await read();
    } finally {
      child.stdin?.end();
      await new Promise<void>((resolve) => {
        child.once("exit", () => resolve());
        child.kill();
      });
    }
  });
});
