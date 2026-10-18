/**
 * A trigger implementation. Receives automation configuration (excluding core
 * host fields) and returns one plain object or `null`.
 */
export type TriggerFunction<
  Params extends Record<string, unknown> = Record<string, unknown>,
  Result extends Record<string, unknown> | null = Record<string, unknown> | null,
> = (params: Params) => Result | Promise<Result>;

/** Map of property name → trigger function (property name becomes the local trigger id). */
export type TriggerMap = Record<string, TriggerFunction<any, any>>;

/** Core automation fields owned by the Rust host — never trigger parameters. */
export const CORE_CONFIG_KEYS = Object.freeze([
  "trigger_type",
  "repository",
  "prompt",
  "profile",
  "checkout",
] as const);

export type CoreConfigKey = (typeof CORE_CONFIG_KEYS)[number];

export const PROTOCOL_VERSION = 2;
