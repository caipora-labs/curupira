import { RegistrationError } from "./errors.js";
import { toKebabCase } from "./names.js";
import type { TriggerFunction, TriggerMap } from "./types.js";

export interface TriggerRegistration {
  /** Local kebab-case trigger name used on the wire. */
  readonly localName: string;
  /** Original object property name. */
  readonly propertyName: string;
  readonly func: TriggerFunction;
}

/**
 * Result of {@link defineTriggers}. Pass this to {@link runExtension} or export
 * it as the package default for a plugin bin.
 */
export interface DefinedTriggers<T extends TriggerMap = TriggerMap> {
  readonly kind: "curupira.defineTriggers";
  /** Original map (preserves TypeScript inference for callers). */
  readonly triggers: T;
  /** Registrations in declaration order. */
  readonly registrations: readonly TriggerRegistration[];
}

function isTriggerMap(value: unknown): value is TriggerMap {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Declare triggers with a plain object. The property name is the default local
 * trigger identifier (converted to kebab-case).
 *
 * @example
 * ```js
 * import { defineTriggers } from "@caipora-labs/curupira-sdk";
 *
 * async function githubIssue({ repository, labels = [] }) {
 *   return { repository, labels };
 * }
 *
 * export default defineTriggers({ githubIssue });
 * ```
 */
export function defineTriggers<const T extends TriggerMap>(
  triggers: T,
): DefinedTriggers<T> {
  if (!isTriggerMap(triggers)) {
    throw new RegistrationError("defineTriggers expects a plain object of functions");
  }
  const registrations: TriggerRegistration[] = [];
  const seen = new Set<string>();
  for (const [propertyName, func] of Object.entries(triggers)) {
    if (typeof func !== "function") {
      throw new RegistrationError(
        `trigger ${JSON.stringify(propertyName)} must be a function`,
      );
    }
    const localName = toKebabCase(propertyName);
    if (seen.has(localName)) {
      throw new RegistrationError(`duplicate trigger name ${JSON.stringify(localName)}`);
    }
    seen.add(localName);
    registrations.push({ localName, propertyName, func });
  }
  if (registrations.length === 0) {
    throw new RegistrationError("defineTriggers requires at least one trigger");
  }
  return {
    kind: "curupira.defineTriggers",
    triggers,
    registrations,
  };
}

/** Type guard for a {@link defineTriggers} result (including default exports). */
export function isDefinedTriggers(value: unknown): value is DefinedTriggers {
  return (
    typeof value === "object" &&
    value !== null &&
    (value as DefinedTriggers).kind === "curupira.defineTriggers" &&
    Array.isArray((value as DefinedTriggers).registrations)
  );
}
