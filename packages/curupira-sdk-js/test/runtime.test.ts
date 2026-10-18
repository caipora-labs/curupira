import assert from "node:assert/strict";
import { PassThrough } from "node:stream";
import { describe, it } from "node:test";

import { defineTriggers } from "../dist/defineTriggers.js";
import { writeFrame } from "../dist/framing.js";
import { createExtensionServer } from "../dist/runtime.js";
import { serveStdio } from "../dist/server.js";
import { PROTOCOL_VERSION } from "../dist/types.js";

type RpcResponse = {
  id: number;
  result?: unknown;
  error?: { code: number; message: string };
};

async function exchange(
  send: (obj: unknown) => void,
  read: () => Promise<RpcResponse>,
  request: unknown,
): Promise<RpcResponse> {
  send(request);
  return read();
}

describe("protocol runtime", () => {
  it("serves initialize, describe, poll (async/sync/null), and shutdown", async () => {
    const stdin = new PassThrough();
    const stdout = new PassThrough();
    let buf = Buffer.alloc(0);

    const defined = defineTriggers({
      githubIssue: async (params: { repo: string; labels?: string[] }) => {
        if (params.repo === "empty/repo") {
          return null;
        }
        return {
          repo: params.repo,
          labels: params.labels ?? [],
          title: "Fix authentication",
        };
      },
      syncProbe: (params: { flag?: boolean }) => ({ flag: params.flag ?? false }),
    });

    const server = createExtensionServer(defined, {
      name: "test-ext",
      version: "0.0.1",
    });
    const serving = serveStdio(server, { stdin, stdout });

    async function read(): Promise<RpcResponse> {
      for (;;) {
        if (buf.length >= 8) {
          const len = Number.parseInt(buf.subarray(0, 8).toString("ascii"), 16);
          if (buf.length >= 8 + len) {
            const body = buf.subarray(8, 8 + len);
            buf = buf.subarray(8 + len);
            return JSON.parse(body.toString("utf8")) as RpcResponse;
          }
        }
        const chunk = await new Promise<Buffer>((resolve) => {
          stdout.once("data", (data: Buffer) => resolve(Buffer.from(data)));
        });
        buf = Buffer.concat([buf, chunk]);
      }
    }

    function send(obj: unknown): void {
      writeFrame(stdin, Buffer.from(JSON.stringify(obj), "utf8"));
    }

    try {
      const init = await exchange(send, read, {
        jsonrpc: "2.0",
        id: 1,
        method: "initialize",
        params: {
          protocol_version: PROTOCOL_VERSION,
          client_info: { name: "t", version: "0" },
        },
      });
      assert.deepEqual(init.result, {
        protocol_version: 2,
        server_info: { name: "test-ext", version: "0.0.1" },
      });

      const described = await exchange(send, read, {
        jsonrpc: "2.0",
        id: 2,
        method: "describe",
        params: {},
      });
      assert.deepEqual(
        (described.result as { triggers: { trigger_type: string }[] }).triggers.map(
          (entry) => entry.trigger_type,
        ),
        ["github-issue", "sync-probe"],
      );

      const none = await exchange(send, read, {
        jsonrpc: "2.0",
        id: 3,
        method: "trigger/poll",
        params: {
          trigger_type: "github-issue",
          automation: {
            repository: "api",
            prompt: "x",
            repo: "empty/repo",
          },
          preview: true,
          limit: 9,
        },
      });
      assert.deepEqual(none.result, { values: null });

      const item = await exchange(send, read, {
        jsonrpc: "2.0",
        id: 4,
        method: "trigger/poll",
        params: {
          trigger_type: "github-issue",
          automation: {
            repository: "api",
            prompt: "x",
            repo: "acme/api",
            labels: ["bug"],
          },
          preview: false,
          limit: 1,
        },
      });
      assert.deepEqual(item.result, {
        values: [
          { key: "repo", value: "acme/api" },
          { key: "labels", value: '["bug"]' },
          { key: "title", value: "Fix authentication" },
        ],
      });

      const syncResult = await exchange(send, read, {
        jsonrpc: "2.0",
        id: 5,
        method: "trigger/poll",
        params: {
          trigger_type: "sync-probe",
          automation: { flag: true },
          preview: false,
          limit: 1,
        },
      });
      assert.deepEqual(syncResult.result, {
        values: [{ key: "flag", value: "true" }],
      });

      const shutdown = await exchange(send, read, {
        jsonrpc: "2.0",
        id: 6,
        method: "shutdown",
        params: {},
      });
      assert.deepEqual(shutdown.result, {});
    } finally {
      stdin.end();
      await serving;
    }
  });
});
