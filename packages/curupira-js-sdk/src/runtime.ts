import {
  RegistrationError,
  RpcError,
  SerializationError,
  ValidationError,
} from "./errors.js";
import type { DefinedTriggers, TriggerRegistration } from "./defineTriggers.js";
import { isDefinedTriggers } from "./defineTriggers.js";
import { serializeTriggerResult } from "./serialize.js";
import { ExtensionServer, serveStdio } from "./server.js";
import { CORE_CONFIG_KEYS } from "./types.js";

export interface ExtensionInfo {
  /** Extension name reported in `initialize` / manifests. */
  name: string;
  /** Extension version reported in `initialize` / manifests. */
  version: string;
  /**
   * Optional TOML template for `--curupira-print-manifest`.
   * Use `{version}` as a placeholder for {@link ExtensionInfo.version}.
   */
  manifestTemplate?: string;
}

function pickAutomationParams(
  configuration: Record<string, unknown>,
): Record<string, unknown> {
  const params: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(configuration)) {
    if ((CORE_CONFIG_KEYS as readonly string[]).includes(key)) {
      continue;
    }
    params[key] = value;
  }
  return params;
}

function findRegistration(
  registrations: readonly TriggerRegistration[],
  triggerType: string,
): TriggerRegistration {
  const local = triggerType.includes("/")
    ? triggerType.slice(triggerType.lastIndexOf("/") + 1)
    : triggerType;
  const match =
    registrations.find((entry) => entry.localName === local) ??
    registrations.find((entry) => entry.localName === triggerType);
  if (!match) {
    throw new RpcError(-32003, `unsupported trigger_type ${JSON.stringify(triggerType)}`);
  }
  return match;
}

async function invokeTrigger(
  registration: TriggerRegistration,
  params: Record<string, unknown>,
): Promise<unknown> {
  return registration.func(params);
}

/** Build a protocol server for the declared triggers (also used in tests). */
export function createExtensionServer(
  defined: DefinedTriggers,
  info: Pick<ExtensionInfo, "name" | "version">,
): ExtensionServer {
  const server = new ExtensionServer({
    name: info.name,
    version: info.version,
    triggers: defined.registrations.map((entry) => ({
      trigger_type: entry.localName,
      prompt_fields: [],
    })),
  });

  server.on("trigger/schema", (params) => {
    const triggerType = (params as { trigger_type?: unknown } | null)?.trigger_type;
    if (typeof triggerType !== "string") {
      throw new RpcError(-32602, "trigger_type is required");
    }
    findRegistration(defined.registrations, triggerType);
    return {
      schema: { type: "object", additionalProperties: true },
      prompt_fields: [],
    };
  });

  server.on("trigger/validate", (params) => {
    const triggerType = (params as { trigger_type?: unknown } | null)?.trigger_type;
    const configuration = {
      ...(((params as { configuration?: Record<string, unknown> } | null)
        ?.configuration ?? {}) as Record<string, unknown>),
    };
    if (typeof triggerType !== "string") {
      throw new RpcError(-32602, "trigger_type is required");
    }
    try {
      findRegistration(defined.registrations, triggerType);
      // JavaScript has no runtime parameter schema. Accept trigger-specific keys
      // as opaque automation configuration (core fields stay host-owned).
      const normalized = { ...configuration };
      return { ok: true, configuration: normalized };
    } catch (err) {
      if (err instanceof RpcError) {
        return { ok: false, error: err.message };
      }
      if (
        err instanceof ValidationError ||
        err instanceof RegistrationError
      ) {
        return { ok: false, error: err.message };
      }
      throw err;
    }
  });

  server.on("trigger/poll", async (params) => {
    const triggerType = (params as { trigger_type?: unknown } | null)?.trigger_type;
    const automation = {
      ...(((params as { automation?: Record<string, unknown> } | null)?.automation ??
        {}) as Record<string, unknown>),
    };
    if (typeof triggerType !== "string") {
      throw new RpcError(-32602, "trigger_type is required");
    }
    const registration = findRegistration(defined.registrations, triggerType);
    try {
      const kwargs = pickAutomationParams(automation);
      const result = await invokeTrigger(registration, kwargs);
      const values = serializeTriggerResult(result, {
        triggerName: registration.localName,
      });
      return { values };
    } catch (err) {
      if (err instanceof RpcError) {
        throw err;
      }
      if (
        err instanceof ValidationError ||
        err instanceof SerializationError ||
        err instanceof RegistrationError
      ) {
        throw new RpcError(-32002, err.message);
      }
      throw new RpcError(
        -32002,
        `execution error: ${err instanceof Error ? err.message : String(err)}`,
      );
    }
  });

  server.on("trigger/onStarted", () => ({}));
  server.on("trigger/onFinished", () => ({}));

  return server;
}

/**
 * Print a filled manifest template to stdout (for `plugins install npm:…`).
 */
export function printManifest(template: string, version: string): void {
  process.stdout.write(`${template.replaceAll("{version}", version)}\n`);
}

/**
 * Serve the extension protocol on stdin/stdout until shutdown or EOF.
 */
export async function runExtension(
  defined: DefinedTriggers,
  info: ExtensionInfo,
): Promise<void> {
  if (!isDefinedTriggers(defined)) {
    throw new RegistrationError(
      "runExtension expects the result of defineTriggers(...)",
    );
  }
  if (process.argv.includes("--curupira-print-manifest")) {
    if (!info.manifestTemplate) {
      throw new RegistrationError(
        "manifestTemplate is required for --curupira-print-manifest",
      );
    }
    printManifest(info.manifestTemplate, info.version);
    return;
  }
  const server = createExtensionServer(defined, info);
  await serveStdio(server);
}

/**
 * Resolve a default export (or the value itself) as {@link DefinedTriggers}
 * and run the protocol server. Convenient for plugin bin entrypoints.
 */
export async function runPluginModule(
  moduleExport: unknown,
  info: ExtensionInfo,
): Promise<void> {
  const defined =
    isDefinedTriggers(moduleExport)
      ? moduleExport
      : isDefinedTriggers(
            (moduleExport as { default?: unknown } | null)?.default,
          )
        ? (moduleExport as { default: DefinedTriggers }).default
        : null;
  if (!defined) {
    throw new RegistrationError(
      "plugin module must default-export defineTriggers({ ... })",
    );
  }
  await runExtension(defined, info);
}
