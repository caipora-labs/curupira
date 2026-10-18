/**
 * Declarative SDK for Curupira process extensions on Node.js.
 *
 * @packageDocumentation
 */

export {
  defineTriggers,
  isDefinedTriggers,
  type DefinedTriggers,
  type TriggerRegistration,
} from "./defineTriggers.js";
export {
  RegistrationError,
  RpcError,
  SerializationError,
  ValidationError,
} from "./errors.js";
export {
  DEFAULT_MAX_FRAME_BYTES,
  log,
  readFrames,
  writeFrame,
} from "./framing.js";
export { toKebabCase, validateTriggerLocalName } from "./names.js";
export {
  createExtensionServer,
  printManifest,
  runExtension,
  runPluginModule,
  type ExtensionInfo,
} from "./runtime.js";
export {
  compactJson,
  serializeTriggerResult,
  stringifyValue,
  toJsonCompatible,
  toKeyValues,
  type KeyValue,
} from "./serialize.js";
export {
  ExtensionServer,
  serveStdio,
  type ExtensionServerOptions,
  type JsonRpcHandler,
  type TriggerDescription,
} from "./server.js";
export {
  CORE_CONFIG_KEYS,
  PROTOCOL_VERSION,
  type CoreConfigKey,
  type TriggerFunction,
  type TriggerMap,
} from "./types.js";
