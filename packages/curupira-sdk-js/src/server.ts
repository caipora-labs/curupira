import { RpcError } from "./errors.js";
import { log, readFrames, writeFrame } from "./framing.js";
import { PROTOCOL_VERSION } from "./types.js";

export type JsonRpcHandler = (params: unknown) => unknown | Promise<unknown>;

export interface TriggerDescription {
  trigger_type: string;
  prompt_fields: string[];
}

export interface ExtensionServerOptions {
  name: string;
  version: string;
  triggers: TriggerDescription[];
}

/** Dispatch initialize / describe / trigger methods to callables. */
export class ExtensionServer {
  readonly name: string;
  readonly version: string;
  readonly triggers: TriggerDescription[];
  private readonly handlers = new Map<string, JsonRpcHandler>();

  constructor(options: ExtensionServerOptions) {
    this.name = options.name;
    this.version = options.version;
    this.triggers = options.triggers;
    this.handlers.set("initialize", (params) => this.initialize(params));
    this.handlers.set("describe", () => this.describe());
    this.handlers.set("shutdown", () => ({}));
  }

  on(method: string, handler: JsonRpcHandler): void {
    this.handlers.set(method, handler);
  }

  /** Look up a registered JSON-RPC method handler. */
  handlerFor(method: string): JsonRpcHandler | undefined {
    return this.handlers.get(method);
  }

  private initialize(params: unknown): Record<string, unknown> {
    const peer = Number(
      (params as { protocol_version?: unknown } | null)?.protocol_version ?? 0,
    );
    if (peer !== PROTOCOL_VERSION) {
      throw new RpcError(-32001, `incompatible protocol version ${peer}`);
    }
    return {
      protocol_version: PROTOCOL_VERSION,
      server_info: { name: this.name, version: this.version },
    };
  }

  private describe(): Record<string, unknown> {
    return { triggers: this.triggers, agents: [] };
  }
}

function writeError(
  stdout: NodeJS.WritableStream,
  id: unknown,
  code: number,
  message: string,
  data?: unknown,
): void {
  const error: Record<string, unknown> = { code, message };
  if (data !== undefined) {
    error.data = data;
  }
  writeFrame(
    stdout,
    Buffer.from(JSON.stringify({ jsonrpc: "2.0", id, error }), "utf8"),
  );
}

/** Serve until EOF or shutdown. stdout is protocol-only; logs go to stderr. */
export async function serveStdio(
  server: ExtensionServer,
  options?: {
    stdin?: AsyncIterable<Buffer | Uint8Array>;
    stdout?: NodeJS.WritableStream;
  },
): Promise<void> {
  const stdin = options?.stdin ?? process.stdin;
  const stdout = options?.stdout ?? process.stdout;
  // Prevent Node from interpreting stdin as text; keep the binary framing intact.
  if (stdin === process.stdin && typeof process.stdin.setEncoding === "function") {
    process.stdin.setEncoding(null as unknown as BufferEncoding);
  }

  for await (const raw of readFrames(stdin)) {
    let request: {
      jsonrpc?: unknown;
      id?: unknown;
      method?: unknown;
      params?: unknown;
    };
    try {
      request = JSON.parse(raw.toString("utf8")) as typeof request;
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      writeError(stdout, null, -32700, `invalid JSON: ${detail}`);
      continue;
    }
    const reqId = request.id;
    const method = request.method;
    if (request.jsonrpc !== "2.0" || typeof method !== "string") {
      writeError(stdout, reqId, -32600, "invalid request");
      continue;
    }
    const handler = server.handlerFor(method);
    if (!handler) {
      writeError(stdout, reqId, -32601, `method not found: ${method}`);
      continue;
    }
    try {
      const result = await handler(request.params);
      writeFrame(
        stdout,
        Buffer.from(JSON.stringify({ jsonrpc: "2.0", id: reqId, result }), "utf8"),
      );
      if (method === "shutdown") {
        return;
      }
    } catch (err) {
      if (err instanceof RpcError) {
        writeError(stdout, reqId, err.code, err.message, err.data);
      } else {
        log(err instanceof Error ? (err.stack ?? err.message) : String(err));
        writeError(
          stdout,
          reqId,
          -32002,
          `execution error: ${err instanceof Error ? err.message : String(err)}`,
        );
      }
    }
  }
}
